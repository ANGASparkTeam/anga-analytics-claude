"""MCP tool definitions. `register_tools(mcp)` attaches whoami, the 10 read-only GA4 tools
and the 5 Search Console tools (gsc_tools)."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from . import ga_credentials, gsc_tools, reports as R
from .config import PropertyConfig, get_registry
from .ga_client import get_client

READ_ONLY = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
)

PropertyArg = Annotated[
    str | None,
    Field(
        description="Property alias from list_properties (e.g. 'main') or a numeric GA4 "
        "property id. Omit to use the default property."
    ),
]
StartArg = Annotated[
    str,
    Field(
        description="Start date, inclusive: YYYY-MM-DD (e.g. '2026-03-01'), 'today', "
        "'yesterday' or 'NdaysAgo' (e.g. '28daysAgo'). Default '28daysAgo'."
    ),
]
EndArg = Annotated[
    str,
    Field(description="End date, inclusive; same formats as start_date. Default 'yesterday'."),
]
CompareArg = Annotated[
    Literal["previous_period", "previous_year", "none"],
    Field(
        description="Comparison window: 'previous_period' = the same number of days right "
        "before the range (default), 'previous_year' = same dates one year earlier, "
        "'none' = no comparison."
    ),
]
LimitArg = Annotated[int, Field(ge=1, le=R.HARD_ROW_CAP, description="Max rows to return.")]

KPI_METRICS = [
    "activeUsers", "newUsers", "sessions", "engagedSessions", "engagementRate",
    "averageSessionDuration", "screenPageViews", "keyEvents", "sessionKeyEventRate",
    "totalRevenue", "ecommercePurchases",
]  # fmt: skip
CHANNEL_METRICS = [
    "sessions", "activeUsers", "engagementRate", "keyEvents", "sessionKeyEventRate", "totalRevenue",
]  # fmt: skip
CHANNEL_DIMENSIONS = ("sessionDefaultChannelGroup", "sessionSourceMedium", "sessionSource")
# GA4 Data API per-request limits.
MAX_METRICS = 10
MAX_DIMENSIONS = 9
TREND_GRANULARITY = {"day": "date", "week": "isoYearIsoWeek", "month": "yearMonth"}
DEFAULT_TREND_METRICS = ["sessions", "activeUsers", "keyEvents"]


# --------------------------------------------------------------------------
# Shared plumbing
# --------------------------------------------------------------------------


def _today(tz: str) -> date:
    return R.today_in(tz)


def _prop(prop: str | None) -> PropertyConfig:
    return get_registry().resolve(prop)


def _window(
    prop: PropertyConfig, start_date: str, end_date: str, compare: str
) -> tuple[date, date, tuple[date, date] | None, date]:
    today = _today(prop.timezone)
    start, end = R.resolve_range(start_date, end_date, today)
    return start, end, R.compute_compare_range(start, end, compare), today


async def _validate(
    prop: PropertyConfig,
    dimensions: list[str] = (),  # type: ignore[assignment]
    metrics: list[str] = (),  # type: ignore[assignment]
    filter_fields: list[str] = (),  # type: ignore[assignment]
) -> None:
    if len(metrics) > MAX_METRICS or len(dimensions) > MAX_DIMENSIONS:
        raise ToolError(
            f"GA4 allows at most {MAX_METRICS} metrics and {MAX_DIMENSIONS} dimensions per "
            f"request (got {len(metrics)} metrics, {len(dimensions)} dimensions). Split it "
            "into several calls."
        )
    meta = await get_client().get_metadata(prop.id)
    errors = [
        *R.validate_fields([*dimensions, *filter_fields], meta.dimension_names, "dimension"),
        *R.validate_fields(metrics, meta.metric_names, "metric"),
    ]
    R.raise_if_invalid(errors)


async def _run(
    prop: PropertyConfig,
    dimensions: list[str],
    metrics: list[str],
    start_date: str,
    end_date: str,
    compare: str,
    *,
    dimension_filter: Any = None,
    order_by: Any = None,
    limit: int | None = 100,
    totals: bool = True,
) -> tuple[R.ReportData, R.ReportData | None, dict, dict | None, list[str]]:
    """Run the current (and optional comparison) report."""
    start, end, cmp_range, today = _window(prop, start_date, end_date, compare)
    client = get_client()

    def req(s: date, e: date, lim: int | None) -> dict[str, Any]:
        return R.build_request(
            dimensions, metrics, s, e,
            dimension_filter=dimension_filter, order_by=order_by, limit=lim, totals=totals,
        )  # fmt: skip

    calls = [client.run_report(prop.id, req(start, end, limit), R.cache_ttl(end, today))]
    if cmp_range:
        # fetch the full comparison set so rows of the current top-N can be matched
        calls.append(
            client.run_report(
                prop.id, req(*cmp_range, R.HARD_ROW_CAP), R.cache_ttl(cmp_range[1], today)
            )
        )
    results = await asyncio.gather(*calls)
    notes = []
    if end >= today:
        notes.append("Range includes today; the most recent data may still be processing.")
    return (
        results[0],
        results[1] if cmp_range else None,
        R.range_dict(start, end),
        R.range_dict(*cmp_range) if cmp_range else None,
        notes,
    )


async def _dimension_report(
    property: str | None,
    start_date: str,
    end_date: str,
    compare: str,
    dimensions: list[str],
    metrics: list[str],
    *,
    dimension_filter: Any = None,
    order_by: Any = None,
    limit: int | None = 100,
    share_of_sessions: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prop = _prop(property)
    cur, prev, dr, cr, notes = await _run(
        prop, dimensions, metrics, start_date, end_date, compare,
        dimension_filter=dimension_filter, order_by=order_by, limit=limit,
    )  # fmt: skip
    rows, truncated = R.shape_rows(cur, prev)
    if share_of_sessions:
        R.add_share(rows, cur)
    meta = R.build_meta(
        [cur, *([prev] if prev else [])],
        row_count=len(rows), truncated=truncated, currency=prop.currency, notes=notes,
        total_rows=cur.row_count,
    )  # fmt: skip
    body: dict[str, Any] = {**(extra or {}), "rows": rows}
    if cur.totals is not None:
        body["totals"] = R.shape_totals(cur, prev)
    return R.make_response(prop.ref(), dr, cr, meta, **body)


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------


async def list_properties(
    search: Annotated[
        str | None,
        Field(description=(
            "Words to find in the client/account name, property name or property id "
            "(case-insensitive, all words must match), e.g. 'acme' or 'acme app'."
        )),
    ] = None,
    limit: Annotated[int, Field(ge=1, le=200, description="Max properties to return.")] = 30,
) -> dict[str, Any]:
    """Find the GA4 property to report on.

    The shared Google account can see hundreds of client accounts, so ALWAYS pass
    `search` with the client or site name the user mentioned (e.g. search='acme'),
    then pass the returned `property_id` as `property` to other tools. Without `search`
    you only get the configured aliases plus the first `limit` properties. If several
    properties match (e.g. web vs app, or staging), ask the user which one.
    """
    registry = get_registry()
    configured = [
        {
            "alias": c.alias, "id": c.id, "name": c.name, "timezone": c.timezone,
            "currency": c.currency, "key_events": list(c.key_events),
            "is_default": c.alias == registry.default,
        }
        for c in registry.properties.values()
    ]  # fmt: skip
    notes: list[str] = []
    try:
        accounts = await get_client().list_accounts()
    except ToolError as exc:
        accounts = []
        notes.append(f"Could not list accessible GA accounts: {exc}")
    flat = [
        {"property_id": p["property_id"], "display_name": p["display_name"],
         "account_name": a["account_name"], "account": a["account"]}
        for a in accounts for p in a["properties"]
    ]  # fmt: skip
    words = (search or "").lower().split()
    matches = [
        p for p in flat
        if all(w in f"{p['account_name']} {p['display_name']} {p['property_id']}".lower() for w in words)
    ]  # fmt: skip
    if search and not matches:
        notes.append(f"No property matches '{search}'. Try a shorter or different word.")
    elif not search and len(flat) > limit:
        notes.append(
            f"Showing {limit} of {len(flat)} properties. Pass `search` with the client name."
        )
    meta = {
        "sampled": False, "thresholded": False, "row_count": min(len(matches), limit),
        "truncated": len(matches) > limit, "cached": False, "currency": None, "notes": notes,
    }  # fmt: skip
    return R.make_response(
        None, None, None, meta,
        default=registry.default, configured_properties=configured,
        total_accessible_accounts=len(accounts), total_accessible_properties=len(flat),
        total_matches=len(matches), properties=matches[:limit],
    )  # fmt: skip


async def kpi_summary(
    property: PropertyArg = None,
    start_date: StartArg = "28daysAgo",
    end_date: EndArg = "yesterday",
    compare: CompareArg = "previous_period",
) -> dict[str, Any]:
    """Headline marketing KPIs for a date range, with period-over-period change.

    Use for "how are we doing?" questions. Returns totals for activeUsers, newUsers,
    sessions, engagedSessions, engagementRate (0-1), averageSessionDuration (seconds),
    screenPageViews, keyEvents, sessionKeyEventRate (0-1), totalRevenue and
    ecommercePurchases. With a comparison each metric is {value, previous, change_pct}
    (change_pct is a percentage, null if previous was 0).

    Examples: last 7 full days -> start_date='7daysAgo', end_date='yesterday';
    March 2026 vs February -> '2026-03-01' to '2026-03-31', compare='previous_period'.
    """
    prop = _prop(property)
    batches = [KPI_METRICS[i : i + MAX_METRICS] for i in range(0, len(KPI_METRICS), MAX_METRICS)]
    results = await asyncio.gather(*(
        _run(prop, [], batch, start_date, end_date, compare, limit=1, totals=False)
        for batch in batches
    ))  # fmt: skip
    metrics: dict[str, Any] = {}
    reports: list[R.ReportData] = []
    for cur, prev, *_ in results:
        metrics |= R.shape_totals(cur, prev)
        reports += [cur, *([prev] if prev else [])]
    _, _, dr, cr, notes = results[0]
    meta = R.build_meta(
        reports, row_count=1, truncated=False, currency=prop.currency, notes=notes,
    )  # fmt: skip
    return R.make_response(prop.ref(), dr, cr, meta, metrics=metrics)


async def channel_performance(
    property: PropertyArg = None,
    start_date: StartArg = "28daysAgo",
    end_date: EndArg = "yesterday",
    compare: CompareArg = "previous_period",
    dimension: Annotated[
        Literal["sessionDefaultChannelGroup", "sessionSourceMedium", "sessionSource"],
        Field(
            description="Grouping: 'sessionDefaultChannelGroup' (Organic Search, Paid Search, "
            "Direct...; default), 'sessionSourceMedium' (e.g. 'google / cpc') or 'sessionSource'."
        ),
    ] = "sessionDefaultChannelGroup",
    limit: LimitArg = 20,
) -> dict[str, Any]:
    """Traffic and conversion performance by acquisition channel (or source/medium).

    Use to compare channels: where sessions come from and which convert. Rows are sorted by
    sessions and include sessions, activeUsers, engagementRate, keyEvents,
    sessionKeyEventRate, totalRevenue and share_of_sessions (fraction of all sessions), each
    with {value, previous, change_pct} when comparing. `totals` covers all rows, not just
    the returned ones.
    """
    if dimension not in CHANNEL_DIMENSIONS:
        raise ToolError(f"dimension must be one of: {', '.join(CHANNEL_DIMENSIONS)}.")
    return await _dimension_report(
        property, start_date, end_date, compare, [dimension], CHANNEL_METRICS,
        limit=limit, share_of_sessions=True, extra={"dimension": dimension},
    )  # fmt: skip


async def campaign_performance(
    property: PropertyArg = None,
    start_date: StartArg = "28daysAgo",
    end_date: EndArg = "yesterday",
    compare: CompareArg = "previous_period",
    campaign_contains: Annotated[
        str | None,
        Field(description="Case-insensitive substring of the campaign name, e.g. 'songkran'."),
    ] = None,
    limit: LimitArg = 50,
) -> dict[str, Any]:
    """Campaign-level performance (sessionCampaignName by sessionSourceMedium).

    Use for questions about specific campaigns (UTM campaign names) or "which campaigns
    drive key events/revenue". Rows sorted by sessions with sessions, activeUsers,
    engagementRate, keyEvents, sessionKeyEventRate, totalRevenue, share_of_sessions.
    Pass `campaign_contains` to narrow to a campaign family. Traffic without a campaign
    shows as '(not set)' or '(direct)'.
    """
    flt = (
        {"field": "sessionCampaignName", "match": "contains", "value": campaign_contains}
        if campaign_contains
        else None
    )
    return await _dimension_report(
        property, start_date, end_date, compare,
        ["sessionCampaignName", "sessionSourceMedium"], CHANNEL_METRICS,
        dimension_filter=flt, limit=limit, share_of_sessions=True,
    )  # fmt: skip


async def page_performance(
    property: PropertyArg = None,
    start_date: StartArg = "28daysAgo",
    end_date: EndArg = "yesterday",
    compare: CompareArg = "previous_period",
    mode: Annotated[
        Literal["landing", "pages"],
        Field(
            description="'landing' = landing pages (where sessions start; sorted by sessions) or "
            "'pages' = all viewed pages by path (sorted by screenPageViews)."
        ),
    ] = "landing",
    path_contains: Annotated[
        str | None, Field(description="Case-insensitive substring of the page path, e.g. '/blog/'.")
    ] = None,
    limit: LimitArg = 50,
) -> dict[str, Any]:
    """Page-level performance: landing pages or all pages.

    Use for "which pages/landing pages perform best or worst", content and SEO/ads landing
    page analysis. Metrics: sessions, activeUsers, engagementRate, keyEvents, bounceRate
    (0-1) and, in 'pages' mode, screenPageViews. Use path_contains to focus on a section.
    """
    if mode == "landing":
        dim, metrics = "landingPage", ["sessions", "activeUsers", "engagementRate", "keyEvents", "bounceRate"]
    elif mode == "pages":
        dim = "pagePath"
        metrics = ["screenPageViews", "sessions", "activeUsers", "engagementRate", "keyEvents", "bounceRate"]
    else:
        raise ToolError("mode must be 'landing' or 'pages'.")
    flt = {"field": dim, "match": "contains", "value": path_contains} if path_contains else None
    return await _dimension_report(
        property, start_date, end_date, compare, [dim], metrics,
        dimension_filter=flt, limit=limit, extra={"mode": mode},
    )  # fmt: skip


async def key_event_breakdown(
    property: PropertyArg = None,
    start_date: StartArg = "28daysAgo",
    end_date: EndArg = "yesterday",
    compare: CompareArg = "previous_period",
    event_names: Annotated[
        list[str] | None,
        Field(
            description="GA event names to count, e.g. ['purchase','generate_lead']. Omit to use "
            "the key events configured for the property, or else every event marked as a key "
            "event in GA4."
        ),
    ] = None,
    by: Annotated[
        str | None,
        Field(
            description="Optional extra dimension to split by, e.g. 'sessionDefaultChannelGroup', "
            "'deviceCategory', 'country'."
        ),
    ] = None,
) -> dict[str, Any]:
    """Counts of conversion (key) events, optionally split by a dimension.

    Use for "how many leads/purchases/sign-ups" and "which channel/device produces them".
    Returns eventCount and totalUsers per eventName (and per `by` value if given). Without
    event_names it uses the property's configured key events, or every event marked as a
    key event in GA4 (event_names in the response is then null).
    """
    prop = _prop(property)
    names = list(event_names or prop.key_events) or None
    dims = ["eventName", by] if by else ["eventName"]
    if by:
        await _validate(prop, dimensions=[by])
    if names:
        flt = {"field": "eventName", "match": "in_list", "value": names}
    else:
        flt = {"field": "isKeyEvent", "match": "exact", "value": "true"}
    return await _dimension_report(
        prop.alias, start_date, end_date, compare, dims, ["eventCount", "totalUsers"],
        dimension_filter=flt, limit=R.HARD_ROW_CAP, extra={"event_names": names},
    )  # fmt: skip


async def trend(
    property: PropertyArg = None,
    start_date: StartArg = "28daysAgo",
    end_date: EndArg = "yesterday",
    metrics: Annotated[
        list[str] | None,
        Field(
            description="GA metric API names, default ['sessions','activeUsers','keyEvents']. "
            "Others: newUsers, engagementRate, screenPageViews, totalRevenue, ..."
        ),
    ] = None,
    granularity: Annotated[
        Literal["day", "week", "month"], Field(description="Bucket size.")
    ] = "day",
) -> dict[str, Any]:
    """Time series of metrics by day, week or month (oldest first).

    Use for "how did X change over time", spotting spikes/drops, or charting. Rows are keyed
    by `date` (YYYY-MM-DD), `isoYearIsoWeek` (2026-W10) or `yearMonth` (2026-03). No
    comparison is computed; call twice with different ranges if needed.
    """
    if granularity not in TREND_GRANULARITY:
        raise ToolError("granularity must be day, week or month.")
    mets = list(metrics or DEFAULT_TREND_METRICS)
    dim = TREND_GRANULARITY[granularity]
    prop = _prop(property)
    await _validate(prop, metrics=mets)
    cur, _, dr, _, notes = await _run(
        prop, [dim], mets, start_date, end_date, "none",
        order_by=dim, limit=R.HARD_ROW_CAP, totals=False,
    )  # fmt: skip
    rows, truncated = R.shape_rows(cur)
    meta = R.build_meta(
        [cur], row_count=len(rows), truncated=truncated, currency=prop.currency, notes=notes,
        total_rows=cur.row_count,
    )  # fmt: skip
    return R.make_response(
        prop.ref(), dr, None, meta, granularity=granularity, dimension=dim, rows=rows
    )


async def realtime_overview(property: PropertyArg = None) -> dict[str, Any]:
    """Who is on the site/app right now (last 30 minutes).

    Use for "is traffic flowing?", checking a campaign launch or email send, or verifying
    tracking. Returns total activeUsers plus the top 10 countries, device categories and
    screens/pages by activeUsers. Realtime data has no date range and no comparison.
    """
    prop = _prop(property)
    client = get_client()
    specs = [
        ("by_country", "country", True),
        ("by_device", "deviceCategory", False),
        ("by_screen", "unifiedScreenName", False),
    ]
    results = await asyncio.gather(
        *(
            client.run_realtime_report(
                prop.id, R.build_realtime_request([dim], ["activeUsers"], 10, totals=totals)
            )
            for _, dim, totals in specs
        )
    )
    body: dict[str, Any] = {"window_minutes": 30}
    first = results[0]
    body["active_users"] = R.shape_totals(first)["activeUsers"] if first.rows or first.totals else 0
    for (key, _, _), data in zip(specs, results, strict=True):
        body[key], _ = R.shape_rows(data)
    meta = R.build_meta(
        list(results), row_count=sum(len(body[k]) for k, _, _ in specs), truncated=False,
        currency=prop.currency, notes=["Top 10 per breakdown; realtime data is cached ~1 minute."],
    )  # fmt: skip
    return R.make_response(prop.ref(), {"window": "last 30 minutes"}, None, meta, **body)


async def get_metadata(
    property: PropertyArg = None,
    search: Annotated[
        str | None,
        Field(
            description="Case-insensitive substring to filter by API name, UI name or description, "
            "e.g. 'revenue', 'campaign', 'event'. Omit to list everything (large)."
        ),
    ] = None,
) -> dict[str, Any]:
    """List the dimensions and metrics available on a property, including custom ones.

    Use before run_report to find exact API names (e.g. search='source' or 'purchase'), or
    to discover the property's custom dimensions/metrics (customEvent:*, customUser:*).
    Descriptions are included only when `search` is given.
    """
    prop = _prop(property)
    md = await get_client().get_metadata(prop.id)
    dims = R.filter_metadata(md.dimensions, search)
    mets = R.filter_metadata(md.metrics, search)
    if not search:
        for item in (*dims, *mets):
            item.pop("description", None)
    meta = R.build_meta(
        [], row_count=len(dims) + len(mets), truncated=False, currency=prop.currency,
        notes=["Metadata is cached for 1 hour."],
    )  # fmt: skip
    return R.make_response(prop.ref(), None, None, meta, dimensions=dims, metrics=mets)


async def run_report(
    dimensions: Annotated[
        list[str],
        Field(description="GA dimension API names, e.g. ['sessionSource','deviceCategory']. May be [] "
              "for totals. Max 9."),
    ],
    metrics: Annotated[
        list[str],
        Field(description="GA metric API names, e.g. ['sessions','keyEvents']. At least 1, max 10."),
    ],
    property: PropertyArg = None,
    start_date: StartArg = "28daysAgo",
    end_date: EndArg = "yesterday",
    dimension_filter: Annotated[
        dict[str, Any] | list[dict[str, Any]] | None,
        Field(
            description="Filter on dimensions: {'field':'country','match':'exact','value':'Thailand'}; "
            "match is exact|contains|begins_with|regex. Pass a list to AND several filters."
        ),
    ] = None,
    order_by: Annotated[
        str | list[str] | None,
        Field(description="Field to sort by; prefix '-' for descending, e.g. '-sessions'. Must be "
              "one of the requested dimensions/metrics. Default: first metric descending."),
    ] = None,
    limit: LimitArg = 100,
) -> dict[str, Any]:
    """Custom GA4 report with any dimensions/metrics (escape hatch).

    Prefer the dedicated tools (kpi_summary, channel_performance, ...) when they fit; use
    this for anything else, e.g. dimensions=['country','deviceCategory'],
    metrics=['activeUsers','keyEvents'], dimension_filter={'field':'country','match':'exact',
    'value':'Thailand'}, order_by='-activeUsers'. Names are validated against the property's
    metadata first and close matches are suggested for typos; use get_metadata to browse.
    Not every dimension/metric pair is compatible; GA's error says which. No comparison is
    computed; run twice for two periods. Returns at most 1000 rows (meta.truncated tells).
    """
    if not metrics:
        raise ToolError("Provide at least one metric.")
    prop = _prop(property)
    flt = R.normalize_filter(dimension_filter)
    filter_fields = [i["field"] for i in flt["and"]] if flt else []
    await _validate(prop, dimensions, metrics, filter_fields)
    cur, _, dr, _, notes = await _run(
        prop, list(dimensions), list(metrics), start_date, end_date, "none",
        dimension_filter=flt, order_by=order_by, limit=limit, totals=False,
    )  # fmt: skip
    rows, truncated = R.shape_rows(cur)
    meta = R.build_meta(
        [cur], row_count=len(rows), truncated=truncated, currency=prop.currency, notes=notes,
        total_rows=cur.row_count,
    )  # fmt: skip
    return R.make_response(
        prop.ref(), dr, None, meta, dimensions=list(dimensions), metrics=list(metrics), rows=rows
    )


async def whoami() -> dict[str, Any]:
    """Check the connection: who is signed in to this connector and whose Google access reads data.

    Use when the user asks to log in / check login ("login", "ล็อกอินแล้วหรือยัง", "เชื่อมต่อได้ไหม")
    or before a first report to confirm the connector works. Returns `signed_in_as` (the
    user's own company email from the connector login, null when auth is disabled
    locally), `data_access` (the shared Google account used to read GA4 and Search Console)
    and `connected: true`. Reads no analytics data.
    """
    from fastmcp.server.dependencies import get_access_token

    from .auth import user_email_from_token

    try:
        email = user_email_from_token(get_access_token())
    except Exception:  # noqa: BLE001 - no auth context (AUTH_DISABLED)
        email = None
    try:
        access = ga_credentials.describe()
    except ValueError as exc:
        access = f"misconfigured: {exc}"
    return {
        "connected": True,
        "signed_in_as": email,
        "data_access": access,
        "note": "Data is read-only through the shared account; your own email is only used "
        "to sign in and for the audit log.",
    }


TOOLS = (
    whoami, list_properties, kpi_summary, channel_performance, campaign_performance, page_performance,
    key_event_breakdown, trend, realtime_overview, get_metadata, run_report,
)  # fmt: skip


def register_tools(mcp: FastMCP) -> None:
    """Register all GA4 and Search Console tools (read-only) on the given FastMCP server."""
    for fn in (*TOOLS, *gsc_tools.TOOLS):
        mcp.tool(fn, annotations=READ_ONLY)
