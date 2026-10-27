from datetime import date

import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from google.analytics.data_v1beta import types as t
from google.api_core import exceptions as gexc

from ga4_mcp import config, ga_client, reports as R, tools
from ga4_mcp.ga_client import GA4Client, map_ga_error

TODAY = date(2026, 10, 27)

METADATA = R.MetadataSet(
    dimensions=[
        {"api_name": n, "ui_name": n, "description": f"desc {n}", "category": "c", "custom": False}
        for n in ("sessionSource", "country", "deviceCategory", "eventName", "date")
    ],
    metrics=[
        {"api_name": n, "ui_name": n, "description": "", "category": "c", "custom": False, "type": "integer"}
        for n in ("sessions", "activeUsers", "keyEvents", "eventCount")
    ],
)


class FakeClient:
    """Stands in for GA4Client; `report` maps a request dict to ReportData."""

    def __init__(self, report=None):
        self.report = report or self.default_report
        self.report_calls: list[dict] = []
        self.realtime_calls: list[dict] = []

    @staticmethod
    def default_report(req):
        cur = req["date_ranges"][0]["end_date"] >= "2026-10-16"
        dims, mets = req["dimensions"], req["metrics"]
        if not dims:
            vals = tuple((200 if cur else 100) for _ in mets)
            return R.ReportData(dims, mets, [((), vals)], 1)
        rows = [((f"v{i}",) * len(dims), tuple((30 - i * 10) * (2 if cur else 1) for _ in mets))
                for i in range(2)]
        return R.ReportData(dims, mets, rows, 2, totals=tuple(60 * (2 if cur else 1) for _ in mets))

    async def run_report(self, property_id, request, ttl):
        self.report_calls.append({"property_id": property_id, "request": request, "ttl": ttl})
        return self.report(request)

    async def run_realtime_report(self, property_id, request):
        self.realtime_calls.append(request)
        d, m = request["dimensions"], request["metrics"]
        return R.ReportData(d, m, [((f"{d[0]}-1",), (7,)), ((f"{d[0]}-2",), (3,))], 2,
                            totals=(10,) if request["totals"] else None)

    async def get_metadata(self, property_id):
        return METADATA

    async def list_accounts(self):
        return [{"account": "1", "account_name": "Acme", "properties": [{"property_id": "123", "display_name": "Site"}]}]


@pytest.fixture
def fake(monkeypatch):
    client = FakeClient()
    ga_client.set_client(client)
    config.set_registry(
        config.parse_properties(
            {
                "default": "main",
                "properties": {
                    "main": {"id": "123", "name": "Site", "currency": "THB", "key_events": ["purchase", "generate_lead"]},
                    "app": {"id": "987", "name": "App"},
                },
            }
        )
    )
    monkeypatch.setattr(tools, "_today", lambda tz: TODAY)
    yield client
    ga_client.set_client(None)
    config.set_registry(None)


@pytest.fixture
def mcp(fake):
    server = FastMCP("test")
    tools.register_tools(server)
    return server


async def call(mcp, name, args=None):
    async with Client(mcp) as c:
        res = await c.call_tool(name, args or {})
    return res.structured_content


# ---- registration -------------------------------------------------------


EXPECTED = {
    "whoami", "list_properties", "kpi_summary", "channel_performance", "campaign_performance",
    "page_performance", "key_event_breakdown", "trend", "realtime_overview", "get_metadata",
    "run_report", "gsc_list_sites", "gsc_performance", "gsc_top_queries", "gsc_top_pages",
    "gsc_page_queries",
}


@pytest.mark.asyncio
async def test_all_tools_registered_read_only_with_docs(mcp):
    async with Client(mcp) as c:
        listed = await c.list_tools()
    assert {x.name for x in listed} == EXPECTED
    for tool in listed:
        assert tool.annotations.read_only_hint is True
        assert len(tool.description) > 80


# ---- end-to-end through the MCP protocol --------------------------------


@pytest.mark.asyncio
async def test_kpi_summary_end_to_end(mcp, fake):
    out = await call(mcp, "kpi_summary", {"start_date": "2026-10-10", "end_date": "2026-10-16"})
    assert out["property"] == {"alias": "main", "id": "123", "name": "Site"}
    assert out["date_range"] == {"start_date": "2026-10-10", "end_date": "2026-10-16", "days": 7}
    assert out["compare_range"]["start_date"] == "2026-10-03"
    assert out["compare_range"]["end_date"] == "2026-10-09"
    assert out["metrics"]["sessions"] == {"value": 200, "previous": 100, "change_pct": 100.0}
    assert set(out["metrics"]) == set(tools.KPI_METRICS)
    assert out["meta"]["currency"] == "THB"
    assert out["meta"]["truncated"] is False
    # 11 KPI metrics -> 2 GA batches (max 10 each), each with a comparison request
    assert len(fake.report_calls) == 4
    # range ended before today -> long TTL
    assert fake.report_calls[0]["ttl"] == R.TTL_HISTORICAL


@pytest.mark.asyncio
async def test_channel_performance_compare_none_and_today_note(mcp, fake):
    out = await call(mcp, "channel_performance",
                     {"start_date": "7daysAgo", "end_date": "today", "compare": "none"})
    assert out["compare_range"] is None
    assert len(fake.report_calls) == 1
    assert fake.report_calls[0]["ttl"] == R.TTL_RECENT
    # relative dates resolved to absolute dates in the property timezone
    assert fake.report_calls[0]["request"]["date_ranges"] == [
        {"start_date": "2026-10-20", "end_date": "2026-10-27"}
    ]
    row = out["rows"][0]
    assert row["sessionDefaultChannelGroup"] == "v0"
    assert row["sessions"] == 60
    assert row["share_of_sessions"] == pytest.approx(0.5)
    assert any("includes today" in n for n in out["meta"]["notes"])


@pytest.mark.asyncio
async def test_property_alias_and_numeric_id(mcp, fake):
    await call(mcp, "kpi_summary", {"property": "app", "compare": "none"})
    await call(mcp, "kpi_summary", {"property": "555", "compare": "none"})
    assert [c["property_id"] for c in fake.report_calls] == ["987", "987", "555", "555"]


@pytest.mark.asyncio
async def test_realtime_overview(mcp):
    out = await call(mcp, "realtime_overview")
    assert out["active_users"] == 10
    assert out["by_country"][0] == {"country": "country-1", "activeUsers": 7}
    assert set(out) >= {"by_device", "by_screen", "meta", "property"}


@pytest.mark.asyncio
async def test_key_event_breakdown_defaults_to_configured_then_ga_key_events(mcp, fake):
    out = await call(mcp, "key_event_breakdown", {"compare": "none"})
    assert out["event_names"] == ["purchase", "generate_lead"]
    flt = fake.report_calls[0]["request"]["dimension_filter"]
    assert flt == {"and": [{"field": "eventName", "match": "in_list",
                            "value": ["purchase", "generate_lead"]}]}
    fake.report_calls.clear()
    out = await call(mcp, "key_event_breakdown", {"property": "app", "compare": "none"})
    assert out["event_names"] is None
    assert fake.report_calls[0]["request"]["dimension_filter"] == {
        "and": [{"field": "isKeyEvent", "match": "exact", "value": "true"}]
    }


def test_realtime_response_without_metadata_converts():
    resp = t.RunRealtimeReportResponse(
        dimension_headers=[t.DimensionHeader(name="country")],
        metric_headers=[t.MetricHeader(name="activeUsers", type_=t.MetricType.TYPE_INTEGER)],
        rows=[t.Row(dimension_values=[t.DimensionValue(value="Thailand")],
                    metric_values=[t.MetricValue(value="7")])],
        row_count=1,
    )  # fmt: skip
    data = ga_client._convert_report(resp)
    assert data.rows == [(("Thailand",), (7,))] and data.sampled is False


@pytest.mark.asyncio
async def test_trend_formats_dates(mcp, fake):
    fake.report = lambda req: R.ReportData(
        req["dimensions"], req["metrics"], [(("20261001",), (5, 3, 1)), (("20261002",), (6, 4, 2))], 2
    )
    out = await call(mcp, "trend", {"start_date": "2026-10-01", "end_date": "2026-10-02"})
    assert [r["date"] for r in out["rows"]] == ["2026-10-01", "2026-10-02"]
    assert out["compare_range"] is None
    assert fake.report_calls[0]["request"]["order_bys"][0]["field"] == "date"


@pytest.mark.asyncio
async def test_run_report_validation_suggests_names(mcp, fake):
    with pytest.raises(ToolError) as exc:
        async with Client(mcp) as c:
            await c.call_tool("run_report", {"dimensions": ["sesionSource"], "metrics": ["sesions"]})
    msg = str(exc.value)
    assert "sessionSource" in msg and "sessions" in msg
    assert fake.report_calls == []


@pytest.mark.asyncio
async def test_run_report_validates_filter_field_and_runs(mcp, fake):
    with pytest.raises(ToolError, match="countri"):
        async with Client(mcp) as c:
            await c.call_tool("run_report", {
                "dimensions": ["country"], "metrics": ["sessions"],
                "dimension_filter": {"field": "countri", "value": "Thailand"}})
    out = await call(mcp, "run_report", {
        "dimensions": ["country"], "metrics": ["sessions"], "start_date": "2026-10-01",
        "end_date": "2026-10-07", "order_by": "-sessions", "limit": 5,
        "dimension_filter": {"field": "country", "match": "exact", "value": "Thailand"}})
    assert out["rows"][0]["country"] == "v0"
    assert out["compare_range"] is None
    req = fake.report_calls[0]["request"]
    assert req["limit"] == 5 and req["order_bys"][0]["desc"] is True


@pytest.mark.asyncio
async def test_run_report_truncated(mcp, fake):
    fake.report = lambda req: R.ReportData(req["dimensions"], req["metrics"],
                                           [(("TH",), (1,))], 4321)
    out = await call(mcp, "run_report", {"dimensions": ["country"], "metrics": ["sessions"]})
    assert out["meta"]["truncated"] is True
    assert out["meta"]["total_rows"] == 4321


@pytest.mark.asyncio
async def test_get_metadata_search(mcp):
    out = await call(mcp, "get_metadata", {"search": "SESSION"})
    assert [d["api_name"] for d in out["dimensions"]] == ["sessionSource"]
    assert [m["api_name"] for m in out["metrics"]] == ["sessions"]
    assert "description" in out["dimensions"][0]
    full = await call(mcp, "get_metadata")
    assert "description" not in full["dimensions"][0]


@pytest.mark.asyncio
async def test_list_properties(mcp):
    out = await call(mcp, "list_properties")
    assert out["default"] == "main"
    assert out["configured_properties"][0]["is_default"] is True
    assert out["properties"][0] == {
        "property_id": "123", "display_name": "Site", "account_name": "Acme", "account": "1",
    }  # fmt: skip
    assert out["total_accessible_properties"] == 1


@pytest.mark.asyncio
async def test_list_properties_search(mcp):
    assert (await call(mcp, "list_properties", {"search": "acme SITE"}))["total_matches"] == 1
    assert (await call(mcp, "list_properties", {"search": "123"}))["total_matches"] == 1
    miss = await call(mcp, "list_properties", {"search": "globex"})
    assert miss["properties"] == [] and "No property matches" in miss["meta"]["notes"][0]


@pytest.mark.asyncio
async def test_kpi_summary_respects_ga_metric_limit(mcp, fake):
    out = await call(mcp, "kpi_summary", {"compare": "none"})
    assert set(out["metrics"]) == set(tools.KPI_METRICS)
    assert len(fake.report_calls) == 2
    assert all(len(c["request"]["metrics"]) <= tools.MAX_METRICS for c in fake.report_calls)


@pytest.mark.asyncio
async def test_run_report_rejects_too_many_metrics(mcp):
    with pytest.raises(ToolError, match="at most 10 metrics"):
        async with Client(mcp) as c:
            await c.call_tool("run_report", {"metrics": [f"m{i}" for i in range(11)], "dimensions": []})


@pytest.mark.asyncio
async def test_bad_input_surfaces_clear_error(mcp):
    with pytest.raises(ToolError, match="Invalid date"):
        async with Client(mcp) as c:
            await c.call_tool("kpi_summary", {"start_date": "last tuesday"})
    with pytest.raises(ToolError, match="Unknown property"):
        async with Client(mcp) as c:
            await c.call_tool("kpi_summary", {"property": "ghost"})


# ---- GA4Client: caching, conversion, error mapping ----------------------


def _proto_response():
    return t.RunReportResponse(
        dimension_headers=[t.DimensionHeader(name="country")],
        metric_headers=[
            t.MetricHeader(name="sessions", type_=t.MetricType.TYPE_INTEGER),
            t.MetricHeader(name="engagementRate", type_=t.MetricType.TYPE_FLOAT),
        ],
        rows=[t.Row(dimension_values=[t.DimensionValue(value="Thailand")],
                    metric_values=[t.MetricValue(value="12"), t.MetricValue(value="0.5")])],
        totals=[t.Row(metric_values=[t.MetricValue(value="12"), t.MetricValue(value="0.5")])],
        row_count=1,
        metadata=t.ResponseMetaData(subject_to_thresholding=True, currency_code="THB"),
        property_quota=t.PropertyQuota(tokens_per_day=t.QuotaStatus(consumed=950, remaining=50)),
    )


@pytest.mark.asyncio
async def test_ga4client_cache_hit_and_conversion():
    calls = []

    class Raw:
        async def run_report(self, request):
            calls.append(request)
            return _proto_response()

    client = GA4Client()
    client._data = Raw()
    req = R.build_request(["country"], ["sessions", "engagementRate"], date(2026, 10, 1),
                          date(2026, 10, 7), dimension_filter={"field": "country", "match": "contains", "value": "thai"},
                          totals=True)
    first = await client.run_report("123", req, 900)
    second = await client.run_report("123", req, 900)
    assert len(calls) == 1
    assert first.cached is False and second.cached is True
    assert first.rows == [(("Thailand",), (12, 0.5))]
    assert isinstance(first.rows[0][1][0], int)
    assert first.totals == (12, 0.5) and first.thresholded and first.currency == "THB"
    assert first.quota["tokens_per_day"] == {"consumed": 950, "remaining": 50}
    assert calls[0].property == "properties/123" and calls[0].return_property_quota is True
    assert calls[0].dimension_filter.filter.string_filter.value == "thai"
    # different request -> miss
    await client.run_report("123", {**req, "limit": 5}, 900)
    assert len(calls) == 2
    meta = R.build_meta([first], row_count=1, truncated=False, currency=None)
    assert meta["quota"]["tokens_per_day"]["remaining_pct"] == 5.0


@pytest.mark.asyncio
async def test_cache_flag_reaches_response_meta(mcp, fake):
    # FakeClient has no cache; emulate one hit to check meta.cached propagation
    fake.report = lambda req: R.ReportData(req["dimensions"], req["metrics"], [], 0, cached=True)
    out = await call(mcp, "run_report", {"dimensions": ["country"], "metrics": ["sessions"]})
    assert out["meta"]["cached"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc", "text"),
    [
        (gexc.ResourceExhausted("quota"), "quota exhausted"),
        (gexc.PermissionDenied("nope"), "Viewer"),
        (gexc.InvalidArgument("bad combo"), "compatible"),
        (gexc.NotFound("x"), "not found"),
    ],
)
async def test_ga_errors_become_tool_errors(exc, text):
    class Raw:
        async def run_report(self, request):
            raise exc

    client = GA4Client()
    client._data = Raw()
    req = R.build_request([], ["sessions"], date(2026, 10, 1), date(2026, 10, 2))
    with pytest.raises(ToolError, match=text):
        await client.run_report("123", req, 900)


def test_map_ga_error_generic():
    assert "Unexpected" in str(map_ga_error(RuntimeError("boom")))


@pytest.mark.asyncio
async def test_whoami_without_auth_reports_connection(mcp):
    out = await call(mcp, "whoami")
    assert out["connected"] is True
    assert out["signed_in_as"] is None
    assert out["data_access"] == "the server's service account"
