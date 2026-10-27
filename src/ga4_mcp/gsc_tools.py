"""Search Console (GSC) tools: organic Google Search clicks, impressions, CTR and position."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Annotated, Any, Literal

from fastmcp.exceptions import ToolError
from pydantic import Field

from . import reports as R
from .gsc_client import get_client

GSC_TZ = "America/Los_Angeles"  # Search Console days are Pacific Time
METRICS = ("clicks", "impressions", "ctr", "position")
# Sites the account can see but not query.
UNUSABLE = {"siteUnverifiedUser"}
DEVICES = {"desktop": "DESKTOP", "mobile": "MOBILE", "tablet": "TABLET"}
SEARCH_TYPES = ("web", "image", "video", "news", "discover", "googleNews")
GRANULARITY = ("none", "day", "week", "month")

SiteArg = Annotated[
    str,
    Field(
        description="Search Console property: an exact site_url from gsc_list_sites "
        "(e.g. 'sc-domain:example.co.th' or 'https://www.example.co.th/'), or a domain such "
        "as 'example.co.th' / 'blog.example.co.th' (the domain property is preferred)."
    ),
]
StartArg = Annotated[
    str,
    Field(
        description="Start date, inclusive: YYYY-MM-DD, 'yesterday' or 'NdaysAgo'. "
        "Default '30daysAgo' (28 days ending 3daysAgo)."
    ),
]
EndArg = Annotated[
    str,
    Field(
        description="End date, inclusive. Default '3daysAgo': Search Console data for the "
        "last ~2-3 days is incomplete."
    ),
]
CompareArg = Annotated[
    Literal["previous_period", "previous_year", "none"],
    Field(
        description="'previous_period' (default) = same number of days right before, "
        "'previous_year' = same dates a year earlier, 'none'."
    ),
]
DeviceArg = Annotated[
    Literal["desktop", "mobile", "tablet"] | None,
    Field(description="Only this device type."),
]
CountryArg = Annotated[
    str | None,
    Field(description="Only this country, ISO 3166-1 alpha-3 code, e.g. 'tha', 'usa'."),
]
SearchTypeArg = Annotated[
    Literal["web", "image", "video", "news", "discover", "googleNews"],
    Field(description="Search surface; default 'web'. 'discover' has no query data."),
]
OrderArg = Annotated[
    Literal["clicks", "impressions"], Field(description="Sort rows by this metric (descending).")
]
LimitArg = Annotated[int, Field(ge=1, le=R.HARD_ROW_CAP, description="Max rows to return.")]


# --------------------------------------------------------------------------
# Shared plumbing
# --------------------------------------------------------------------------


def _today() -> date:
    return R.today_in(GSC_TZ)


def _host(site_url: str) -> str:
    """'sc-domain:x.com' / 'https://www.x.com/path/' -> 'x.com' / 'www.x.com/path'."""
    s = site_url.strip().lower().removeprefix("sc-domain:")
    s = s.split("://", 1)[-1]
    return s.rstrip("/")


def _bare(host: str) -> str:
    return host.removeprefix("www.")


def _rank(site_url: str) -> int:
    """Preference among properties of the same domain: domain property, https, http."""
    if site_url.startswith("sc-domain:"):
        return 0
    return 1 if site_url.startswith("https://") else 2


async def _resolve_site(site: str) -> str:
    """Map a site_url or a domain to one queryable Search Console property."""
    if not site or not site.strip():
        raise ToolError("Pass `site`: a site_url from gsc_list_sites or a domain.")
    sites = await get_client().list_sites()
    usable = [s for s in sites if s["permission"] not in UNUSABLE]
    exact = next((s for s in sites if s["site_url"] == site.strip()), None)
    if exact:
        if exact["permission"] in UNUSABLE:
            raise ToolError(
                f"{exact['site_url']} is not verified for the shared account "
                "(siteUnverifiedUser), so it cannot be queried. Ask the site owner to re-add it."
            )
        return exact["site_url"]
    want = _bare(_host(site))
    same = [s["site_url"] for s in usable if _bare(_host(s["site_url"])) == want]
    if not same:
        # Domain properties cover subdomains (blog.x.com is inside sc-domain:x.com).
        same = [
            s["site_url"] for s in usable
            if s["site_url"].startswith("sc-domain:") and want.endswith("." + _host(s["site_url"]))
        ]  # fmt: skip
    if same:
        return sorted(same, key=_rank)[0]
    near = [s["site_url"] for s in usable if want.split("/")[0] in s["site_url"].lower()]
    hint = f" Close matches: {', '.join(near[:8])}." if near else " Use gsc_list_sites(search=...)."
    raise ToolError(f"No queryable Search Console property for '{site}'.{hint}")


def _window(start_date: str, end_date: str, compare: str):
    today = _today()
    start, end = R.resolve_range(start_date, end_date, today)
    return start, end, R.compute_compare_range(start, end, compare), today


def _filters(
    *, query_contains: str | None = None, page: str | None = None, page_contains: str | None = None,
    country: str | None = None, device: str | None = None,
) -> list[dict[str, Any]]:
    out = []
    if query_contains:
        out.append({"dimension": "query", "operator": "contains", "expression": query_contains})
    if page:
        out.append({"dimension": "page", "operator": "equals", "expression": page})
    if page_contains:
        out.append({"dimension": "page", "operator": "contains", "expression": page_contains})
    if country:
        out.append({"dimension": "country", "operator": "equals", "expression": country.lower()})
    if device:
        if device not in DEVICES:
            raise ToolError(f"device must be one of: {', '.join(DEVICES)}.")
        out.append({"dimension": "device", "operator": "equals", "expression": DEVICES[device]})
    return out


def _body(
    dimensions: list[str], start: date, end: date, filters: list[dict[str, Any]],
    search_type: str, limit: int,
) -> dict[str, Any]:
    if search_type not in SEARCH_TYPES:
        raise ToolError(f"search_type must be one of: {', '.join(SEARCH_TYPES)}.")
    body: dict[str, Any] = {
        "startDate": start.isoformat(), "endDate": end.isoformat(),
        "dimensions": dimensions, "type": search_type, "rowLimit": limit,
    }  # fmt: skip
    if filters:
        body["dimensionFilterGroups"] = [{"groupType": "and", "filters": filters}]
    return body


def _values(row: dict[str, Any]) -> dict[str, float]:
    return {
        "clicks": int(row.get("clicks", 0)),
        "impressions": int(row.get("impressions", 0)),
        "ctr": round(float(row.get("ctr", 0)), 4),
        "position": round(float(row.get("position", 0)), 1),
    }


def _entry(name: str, value: float, previous: float | None, compare: bool) -> Any:
    if not compare:
        return value
    prev = previous or 0
    entry = {"value": value, "previous": prev, "change_pct": R.pct_change(value, prev)}
    if name == "position":
        # Lower is better; a negative change is an improvement.
        entry["change"] = round(value - prev, 1) if prev else None
    return entry


def _shape(
    dimensions: list[str], cur: list[dict[str, Any]], prev: list[dict[str, Any]] | None
) -> list[dict[str, Any]]:
    compare = prev is not None
    prev_map = {tuple(r.get("keys", [])): _values(r) for r in prev or []}
    out = []
    for r in cur:
        keys = tuple(r.get("keys", []))
        row: dict[str, Any] = dict(zip(dimensions, keys, strict=True))
        pv = prev_map.get(keys, {})
        row |= {m: _entry(m, v, pv.get(m), compare) for m, v in _values(r).items()}
        out.append(row)
    return out


async def _report(
    site: str, dimensions: list[str], start_date: str, end_date: str, compare: str,
    filters: list[dict[str, Any]], search_type: str, limit: int, order_by: str = "clicks",
) -> tuple[str, list[dict[str, Any]], dict, dict | None, dict]:
    """Run current (and comparison) searchAnalytics queries; rows shaped and sorted."""
    site_url = await _resolve_site(site)
    start, end, cmp_range, today = _window(start_date, end_date, compare)
    client = get_client()
    # GSC always returns rows by clicks; to rank by impressions fetch more and re-sort.
    fetch = R.HARD_ROW_CAP if dimensions and order_by == "impressions" else limit
    calls = [
        client.query(
            site_url, _body(dimensions, start, end, filters, search_type, fetch),
            R.cache_ttl(end, today),
        )
    ]  # fmt: skip
    if cmp_range:
        # A wider comparison set so this period's rows find their previous values.
        calls.append(
            client.query(
                site_url,
                _body(dimensions, *cmp_range, filters, search_type,
                      R.HARD_ROW_CAP if dimensions else 1),
                R.cache_ttl(cmp_range[1], today),
            )
        )  # fmt: skip
    results = await asyncio.gather(*calls)
    cur_rows = sorted(results[0][0], key=lambda r: r.get(order_by, 0), reverse=True)
    truncated = bool(dimensions) and len(cur_rows) >= fetch
    rows = _shape(dimensions, cur_rows[:limit], results[1][0] if cmp_range else None)
    notes = []
    if end >= today - timedelta(days=2):
        notes.append("The last 2-3 days of Search Console data are still incomplete.")
    if truncated:
        notes.append(f"Only the top {len(rows)} rows were returned; raise limit or add a filter.")
    meta = {
        "sampled": False, "thresholded": False, "row_count": len(rows), "truncated": truncated,
        "cached": all(cached for _, cached in results), "currency": None, "notes": notes,
    }  # fmt: skip
    return (
        site_url, rows, R.range_dict(start, end),
        R.range_dict(*cmp_range) if cmp_range else None, meta,
    )  # fmt: skip


def _response(site_url: str, dr: dict, cr: dict | None, meta: dict, **body: Any) -> dict:
    return R.make_response({"site_url": site_url}, dr, cr, meta, **body)


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------


async def gsc_list_sites(
    search: Annotated[
        str | None,
        Field(description="Words to find in the site URL (case-insensitive, all must match), "
              "e.g. 'acme'."),
    ] = None,
    limit: Annotated[int, Field(ge=1, le=500, description="Max sites to return.")] = 30,
) -> dict[str, Any]:
    """Find the Google Search Console property to report on.

    The shared Google account sees hundreds of client sites, so ALWAYS pass `search` with
    the client or domain name (e.g. search='acme'). Each site has site_url (pass it as
    `site` to the other gsc_* tools), type ('domain' covers all subdomains and protocols;
    'url_prefix' covers one URL prefix), permission and queryable (false for
    'siteUnverifiedUser'). A GA4 property and a GSC site usually share the domain.
    """
    sites = await get_client().list_sites()
    words = (search or "").lower().split()
    matches = [
        {
            "site_url": s["site_url"],
            "type": "domain" if s["site_url"].startswith("sc-domain:") else "url_prefix",
            "permission": s["permission"],
            "queryable": s["permission"] not in UNUSABLE,
        }
        for s in sorted(sites, key=lambda s: (_bare(_host(s["site_url"])), _rank(s["site_url"])))
        if all(w in s["site_url"].lower() for w in words)
    ]
    notes = []
    if search and not matches:
        notes.append(f"No site matches '{search}'. Try a shorter word or the bare domain.")
    elif not search and len(matches) > limit:
        notes.append(f"Showing {limit} of {len(matches)} sites. Pass `search` with the domain.")
    meta = {
        "sampled": False, "thresholded": False, "row_count": min(len(matches), limit),
        "truncated": len(matches) > limit, "cached": False, "currency": None, "notes": notes,
    }  # fmt: skip
    return R.make_response(
        None, None, None, meta,
        total_accessible_sites=len(sites),
        total_queryable_sites=sum(s["permission"] not in UNUSABLE for s in sites),
        total_matches=len(matches), sites=matches[:limit],
    )  # fmt: skip


async def gsc_performance(
    site: SiteArg,
    start_date: StartArg = "30daysAgo",
    end_date: EndArg = "3daysAgo",
    compare: CompareArg = "previous_period",
    granularity: Annotated[
        Literal["none", "day", "week", "month"],
        Field(description="'none' (default) = totals only; 'day' adds a daily series "
              "('week'/'month' aggregate the days)."),
    ] = "none",
    device: DeviceArg = None,
    country: CountryArg = None,
    search_type: SearchTypeArg = "web",
) -> dict[str, Any]:
    """Organic Google Search totals for a site: clicks, impressions, ctr (0-1), position.

    Use for "how is SEO / organic search doing?". With a comparison each metric is
    {value, previous, change_pct}; position (average rank, lower is better) also has
    `change` in places (negative = improved). Set granularity to get a time series in
    `rows` (oldest first). Totals include anonymized queries, so they are larger than the
    sum of gsc_top_queries rows.
    """
    if granularity not in GRANULARITY:
        raise ToolError(f"granularity must be one of: {', '.join(GRANULARITY)}.")
    filters = _filters(country=country, device=device)
    site_url, totals, dr, cr, meta = await _report(
        site, [], start_date, end_date, compare, filters, search_type, 1
    )
    metrics = totals[0] if totals else {m: _entry(m, 0, 0, cr is not None) for m in METRICS}
    body: dict[str, Any] = {"metrics": metrics}
    if granularity != "none":
        start, end, _, today = _window(start_date, end_date, "none")
        rows, _ = await get_client().query(
            site_url, _body(["date"], start, end, filters, search_type, R.HARD_ROW_CAP),
            R.cache_ttl(end, today),
        )  # fmt: skip
        body["granularity"] = granularity
        body["rows"] = _bucket(sorted(rows, key=lambda r: r["keys"][0]), granularity)
        meta["row_count"] = len(body["rows"])
        if granularity != "day":
            meta["notes"].append(f"The first and last {granularity} may be partial.")
    return _response(site_url, dr, cr, meta, **body)


def _bucket(daily: list[dict[str, Any]], granularity: str) -> list[dict[str, Any]]:
    def key(day: str) -> str:
        if granularity == "day":
            return day
        d = date.fromisoformat(day)
        if granularity == "week":
            y, w, _ = d.isocalendar()
            return f"{y}-W{w:02d}"
        return day[:7]

    buckets: dict[str, dict[str, float]] = {}
    for r in daily:
        b = buckets.setdefault(key(r["keys"][0]), {"clicks": 0, "impressions": 0, "pos_w": 0.0})
        b["clicks"] += r.get("clicks", 0)
        b["impressions"] += r.get("impressions", 0)
        b["pos_w"] += r.get("position", 0) * r.get("impressions", 0)
    field = {"day": "date", "week": "isoYearIsoWeek", "month": "yearMonth"}[granularity]
    return [
        {
            field: k, "clicks": int(b["clicks"]), "impressions": int(b["impressions"]),
            "ctr": round(b["clicks"] / b["impressions"], 4) if b["impressions"] else 0,
            "position": round(b["pos_w"] / b["impressions"], 1) if b["impressions"] else 0,
        }
        for k, b in buckets.items()
    ]  # fmt: skip


async def gsc_top_queries(
    site: SiteArg,
    start_date: StartArg = "30daysAgo",
    end_date: EndArg = "3daysAgo",
    compare: CompareArg = "previous_period",
    query_contains: Annotated[
        str | None, Field(description="Only queries containing this text, e.g. 'สินเชื่อ'.")
    ] = None,
    page_contains: Annotated[
        str | None, Field(description="Only queries landing on URLs containing this, e.g. '/loan/'.")
    ] = None,
    device: DeviceArg = None,
    country: CountryArg = None,
    order_by: OrderArg = "clicks",
    limit: LimitArg = 50,
) -> dict[str, Any]:
    """Top Google Search queries (keywords) for a site with clicks, impressions, ctr, position.

    Use for "which keywords bring traffic", keyword gains/losses, brand vs non-brand (filter
    with query_contains) or content gaps (sort by impressions: high impressions + low ctr =
    opportunity). Each metric is {value, previous, change_pct} when comparing; queries new
    this period have previous 0. Anonymized (rare) queries are never listed.
    """
    filters = _filters(query_contains=query_contains, page_contains=page_contains,
                       country=country, device=device)  # fmt: skip
    site_url, rows, dr, cr, meta = await _report(
        site, ["query"], start_date, end_date, compare, filters, "web", limit, order_by
    )
    return _response(site_url, dr, cr, meta, order_by=order_by, rows=rows)


async def gsc_top_pages(
    site: SiteArg,
    start_date: StartArg = "30daysAgo",
    end_date: EndArg = "3daysAgo",
    compare: CompareArg = "previous_period",
    page_contains: Annotated[
        str | None, Field(description="Only URLs containing this, e.g. '/blog/'.")
    ] = None,
    query_contains: Annotated[
        str | None, Field(description="Only traffic from queries containing this text.")
    ] = None,
    device: DeviceArg = None,
    country: CountryArg = None,
    order_by: OrderArg = "clicks",
    limit: LimitArg = 50,
) -> dict[str, Any]:
    """Top pages (full URLs) in Google Search for a site with clicks, impressions, ctr, position.

    Use for "which pages get organic traffic", pages that gained or lost clicks, or (with
    order_by='impressions') pages that show up but are not clicked. Pair with
    gsc_page_queries to see the keywords behind one page and with GA4 page_performance
    (landing mode) for on-site engagement and key events.
    """
    filters = _filters(query_contains=query_contains, page_contains=page_contains,
                       country=country, device=device)  # fmt: skip
    site_url, rows, dr, cr, meta = await _report(
        site, ["page"], start_date, end_date, compare, filters, "web", limit, order_by
    )
    return _response(site_url, dr, cr, meta, order_by=order_by, rows=rows)


async def gsc_page_queries(
    site: SiteArg,
    page: Annotated[
        str,
        Field(description="The page: a full URL as shown by gsc_top_pages (exact match), or a "
              "path fragment such as '/home-loan' (contains match)."),
    ],
    start_date: StartArg = "30daysAgo",
    end_date: EndArg = "3daysAgo",
    compare: CompareArg = "previous_period",
    device: DeviceArg = None,
    country: CountryArg = None,
    order_by: OrderArg = "clicks",
    limit: LimitArg = 50,
) -> dict[str, Any]:
    """The search queries that bring Google traffic to one page.

    Use to explain why a page gained or lost organic clicks, to check which keywords a page
    ranks for, or to find keyword cannibalisation (also try gsc_top_queries with
    query_contains, then compare pages). Rows are queries with clicks, impressions, ctr
    and position (with comparison).
    """
    if not page or not page.strip():
        raise ToolError("Pass `page`: a full URL or a path fragment.")
    page = page.strip()
    exact = page.startswith(("http://", "https://"))
    filters = _filters(page=page if exact else None, page_contains=None if exact else page,
                       country=country, device=device)  # fmt: skip
    site_url, rows, dr, cr, meta = await _report(
        site, ["query"], start_date, end_date, compare, filters, "web", limit, order_by
    )
    return _response(
        site_url, dr, cr, meta, page=page, page_match="exact" if exact else "contains",
        order_by=order_by, rows=rows,
    )  # fmt: skip


TOOLS = (gsc_list_sites, gsc_performance, gsc_top_queries, gsc_top_pages, gsc_page_queries)
