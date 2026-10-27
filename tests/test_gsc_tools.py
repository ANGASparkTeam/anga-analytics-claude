from datetime import date

import httpx
import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from google.auth import exceptions as auth_exc

from ga4_mcp import gsc_client, gsc_tools, tools
from ga4_mcp.gsc_client import map_gsc_error

TODAY = date(2026, 10, 27)
SITES = [
    {"site_url": "sc-domain:acme.co.th", "permission": "siteOwner"},
    {"site_url": "https://www.acme.co.th/", "permission": "siteFullUser"},
    {"site_url": "https://blog.other.com/", "permission": "siteRestrictedUser"},
    {"site_url": "https://www.other.com/", "permission": "siteFullUser"},
    {"site_url": "https://landing.other.com/", "permission": "siteUnverifiedUser"},
]


class FakeGSC:
    """Stands in for GSCClient; current period (ends after 10-01) has doubled numbers."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def list_sites(self):
        return SITES

    async def query(self, site_url, body, ttl):
        self.calls.append((site_url, body))
        k = 2 if body["endDate"] > "2026-10-01" else 1
        dims = body["dimensions"]
        if not dims:
            return [{"clicks": 100 * k, "impressions": 1000 * k, "ctr": 0.1, "position": 8 - k}], False
        if dims == ["date"]:
            return [
                {"keys": ["2026-10-02"], "clicks": 10, "impressions": 100, "position": 4.0},
                {"keys": ["2026-10-01"], "clicks": 5, "impressions": 300, "position": 8.0},
            ], False
        rows = [
            {"keys": ["loan"], "clicks": 50 * k, "impressions": 500, "ctr": 0.1 * k, "position": 3.0},
            {"keys": ["deposit"], "clicks": 10 * k, "impressions": 900, "ctr": 0.011, "position": 9.0},
        ]
        if k == 2:
            rows.append({"keys": ["new kw"], "clicks": 1, "impressions": 5, "ctr": 0.2, "position": 20})
        return rows[: body["rowLimit"]], False


@pytest.fixture
def fake(monkeypatch):
    client = FakeGSC()
    gsc_client.set_client(client)
    monkeypatch.setattr(gsc_tools, "_today", lambda: TODAY)
    yield client
    gsc_client.set_client(None)


@pytest.fixture
def mcp(fake):
    server = FastMCP("test")
    tools.register_tools(server)
    return server


async def call(mcp, name, args=None):
    async with Client(mcp) as c:
        res = await c.call_tool(name, args or {})
    return res.structured_content


# ---- site resolution ----------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "given, expected",
    [
        ("sc-domain:acme.co.th", "sc-domain:acme.co.th"),
        ("https://www.acme.co.th/", "https://www.acme.co.th/"),
        ("acme.co.th", "sc-domain:acme.co.th"),  # domain property preferred
        ("www.acme.co.th", "sc-domain:acme.co.th"),
        ("https://shop.acme.co.th", "sc-domain:acme.co.th"),  # subdomain inside domain property
        ("blog.other.com", "https://blog.other.com/"),
        ("other.com", "https://www.other.com/"),
    ],
)
async def test_resolve_site(fake, given, expected):
    assert await gsc_tools._resolve_site(given) == expected


@pytest.mark.asyncio
async def test_resolve_site_rejects_unverified_and_unknown(fake):
    with pytest.raises(ToolError, match="not verified"):
        await gsc_tools._resolve_site("https://landing.other.com/")
    with pytest.raises(ToolError, match="Close matches"):
        await gsc_tools._resolve_site("other")
    with pytest.raises(ToolError, match="gsc_list_sites"):
        await gsc_tools._resolve_site("nothing.example")


# ---- tools ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_gsc_list_sites_search(mcp):
    out = await call(mcp, "gsc_list_sites", {"search": "other"})
    assert out["total_accessible_sites"] == 5
    assert out["total_queryable_sites"] == 4
    assert [s["site_url"] for s in out["sites"]] == [
        "https://blog.other.com/", "https://landing.other.com/", "https://www.other.com/",
    ]  # fmt: skip
    assert out["sites"][1]["queryable"] is False
    full = await call(mcp, "gsc_list_sites", {"search": "acme"})
    assert full["sites"][0] == {
        "site_url": "sc-domain:acme.co.th", "type": "domain", "permission": "siteOwner",
        "queryable": True,
    }  # fmt: skip


@pytest.mark.asyncio
async def test_gsc_performance_totals_with_compare(mcp, fake):
    out = await call(mcp, "gsc_performance", {"site": "acme.co.th"})
    assert out["property"] == {"site_url": "sc-domain:acme.co.th"}
    assert out["date_range"]["start_date"] == "2026-09-27"
    assert out["date_range"]["end_date"] == "2026-10-24"
    assert out["compare_range"]["end_date"] == "2026-09-26"
    m = out["metrics"]
    assert m["clicks"] == {"value": 200, "previous": 100, "change_pct": 100.0}
    assert m["position"]["value"] == 6.0 and m["position"]["change"] == -1.0
    assert fake.calls[0][1]["type"] == "web" and "dimensionFilterGroups" not in fake.calls[0][1]


@pytest.mark.asyncio
async def test_gsc_performance_weekly_series_and_filters(mcp, fake):
    out = await call(mcp, "gsc_performance", {
        "site": "acme.co.th", "compare": "none", "granularity": "week",
        "device": "mobile", "country": "THA",
    })  # fmt: skip
    assert out["compare_range"] is None
    assert out["metrics"]["clicks"] == 200
    assert out["rows"] == [
        {"isoYearIsoWeek": "2026-W40", "clicks": 15, "impressions": 400, "ctr": 0.0375, "position": 7.0}
    ]
    filters = fake.calls[0][1]["dimensionFilterGroups"][0]["filters"]
    assert {"dimension": "device", "operator": "equals", "expression": "MOBILE"} in filters
    assert {"dimension": "country", "operator": "equals", "expression": "tha"} in filters


@pytest.mark.asyncio
async def test_gsc_top_queries_compare_and_new_rows(mcp, fake):
    out = await call(mcp, "gsc_top_queries", {"site": "acme.co.th", "query_contains": "lo"})
    rows = out["rows"]
    assert [r["query"] for r in rows] == ["loan", "deposit", "new kw"]
    assert rows[0]["clicks"] == {"value": 100, "previous": 50, "change_pct": 100.0}
    assert rows[2]["clicks"]["previous"] == 0 and rows[2]["clicks"]["change_pct"] is None
    body = fake.calls[0][1]
    assert body["dimensions"] == ["query"]
    assert body["dimensionFilterGroups"][0]["filters"] == [
        {"dimension": "query", "operator": "contains", "expression": "lo"}
    ]
    assert fake.calls[1][1]["rowLimit"] == 1000  # wide comparison set


@pytest.mark.asyncio
async def test_gsc_top_pages_order_by_impressions_and_truncation(mcp, fake):
    out = await call(mcp, "gsc_top_pages", {
        "site": "acme.co.th", "compare": "none", "order_by": "impressions", "limit": 2,
    })  # fmt: skip
    assert [r["page"] for r in out["rows"]] == ["deposit", "loan"]
    assert fake.calls[0][1]["rowLimit"] == 1000  # fetched wide, then re-sorted
    assert out["meta"]["truncated"] is False
    out = await call(mcp, "gsc_top_pages", {"site": "acme.co.th", "compare": "none", "limit": 2})
    assert out["meta"]["truncated"] is True and len(out["rows"]) == 2


@pytest.mark.asyncio
async def test_gsc_page_queries_exact_vs_contains(mcp, fake):
    out = await call(mcp, "gsc_page_queries", {
        "site": "acme.co.th", "page": "https://www.acme.co.th/loan", "compare": "none",
    })  # fmt: skip
    assert out["page_match"] == "exact"
    assert fake.calls[0][1]["dimensionFilterGroups"][0]["filters"] == [
        {"dimension": "page", "operator": "equals", "expression": "https://www.acme.co.th/loan"}
    ]
    out = await call(mcp, "gsc_page_queries", {"site": "acme.co.th", "page": "/loan", "compare": "none"})
    assert out["page_match"] == "contains"
    assert fake.calls[-1][1]["dimensionFilterGroups"][0]["filters"][0]["operator"] == "contains"


@pytest.mark.asyncio
async def test_recent_end_date_notes_incomplete_data(mcp):
    out = await call(mcp, "gsc_performance", {"site": "acme.co.th", "end_date": "yesterday"})
    assert any("incomplete" in n for n in out["meta"]["notes"])


# ---- client ---------------------------------------------------------------


def _http_error(status, body):
    req = httpx.Request("POST", "https://x")
    return httpx.HTTPStatusError("e", request=req, response=httpx.Response(status, json=body, request=req))


@pytest.mark.parametrize(
    "exc, text",
    [
        (_http_error(403, {"error": {"message": "no access"}}), "Permission denied for s"),
        (_http_error(429, {"error": {"message": "slow"}}), "quota exhausted"),
        (_http_error(400, {"error": {"message": "bad dim"}}), "rejected the request for s: bad dim"),
        (_http_error(503, {}), "temporarily unavailable"),
        (_http_error(401, {"error": {"message": "x"}}), "could not authenticate"),
        (auth_exc.RefreshError("invalid_scope"), "webmasters.readonly"),
    ],
)
def test_map_gsc_error(exc, text):
    assert text in str(map_gsc_error(exc, "s"))


class _Creds:
    valid = True
    token = "tok"


@pytest.mark.asyncio
async def test_gsc_client_query_caches_and_encodes_site(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"rows": [{"keys": ["a"], "clicks": 1}]})

    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient
    monkeypatch.setattr(gsc_client.httpx, "AsyncClient", lambda **kw: real(transport=transport, **kw))
    client = gsc_client.GSCClient()
    client._credentials = _Creds()
    body = {"startDate": "2026-10-01", "endDate": "2026-10-02", "dimensions": ["query"]}
    rows, cached = await client.query("sc-domain:acme.co.th", body, 60)
    assert rows == [{"keys": ["a"], "clicks": 1}] and cached is False
    assert seen[0].url.raw_path.endswith(b"/sites/sc-domain%3Aacme.co.th/searchAnalytics/query")
    assert seen[0].headers["authorization"] == "Bearer tok"
    rows2, cached2 = await client.query("sc-domain:acme.co.th", body, 60)
    assert cached2 is True and len(seen) == 1
