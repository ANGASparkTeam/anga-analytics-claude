from datetime import date, datetime, timezone

import pytest
from fastmcp.exceptions import ToolError

from ga4_mcp import reports as R
from ga4_mcp.config import parse_properties

TODAY = date(2026, 10, 27)


def data(dims, metrics, rows, **kw):
    return R.ReportData(
        dimensions=dims,
        metrics=metrics,
        rows=[(tuple(d), tuple(v)) for d, v in rows],
        row_count=kw.pop("row_count", len(rows)),
        **kw,
    )


# ---- dates --------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("today", date(2026, 10, 27)),
        ("yesterday", date(2026, 10, 26)),
        ("7daysAgo", date(2026, 10, 20)),
        ("0daysAgo", TODAY),
        ("2026-03-01", date(2026, 3, 1)),
    ],
)
def test_resolve_date(value, expected):
    assert R.resolve_date(value, TODAY) == expected


@pytest.mark.parametrize("bad", ["last week", "2026-13-01", "daysAgo", ""])
def test_resolve_date_invalid(bad):
    with pytest.raises(ToolError, match="Invalid date"):
        R.resolve_date(bad, TODAY)


def test_resolve_range_rejects_reversed():
    with pytest.raises(ToolError, match="after end_date"):
        R.resolve_range("2026-03-10", "2026-03-01", TODAY)


def test_today_uses_property_timezone():
    now = datetime(2026, 10, 26, 20, 0, tzinfo=timezone.utc)  # 03:00 next day in Bangkok
    assert R.today_in("Asia/Bangkok", now) == date(2026, 10, 27)
    assert R.today_in("UTC", now) == date(2026, 10, 26)


def test_previous_period_same_length_directly_before():
    assert R.compute_compare_range(date(2026, 3, 1), date(2026, 3, 31), "previous_period") == (
        date(2026, 1, 29),
        date(2026, 2, 28),
    )
    assert R.compute_compare_range(date(2026, 10, 27), date(2026, 10, 27), "previous_period") == (
        date(2026, 10, 26),
        date(2026, 10, 26),
    )


def test_previous_year_handles_leap_day():
    assert R.compute_compare_range(date(2026, 3, 1), date(2026, 3, 31), "previous_year") == (
        date(2025, 3, 1),
        date(2025, 3, 31),
    )
    assert R.compute_compare_range(date(2024, 2, 29), date(2024, 3, 5), "previous_year") == (
        date(2023, 2, 28),
        date(2023, 3, 5),
    )


def test_compare_none_and_invalid():
    assert R.compute_compare_range(date(2026, 3, 1), date(2026, 3, 2), "none") is None
    with pytest.raises(ToolError):
        R.compute_compare_range(date(2026, 3, 1), date(2026, 3, 2), "yoy")


def test_cache_ttl():
    assert R.cache_ttl(date(2026, 10, 26), TODAY) == 15 * 60
    assert R.cache_ttl(TODAY, TODAY) == 3 * 60


# ---- change math --------------------------------------------------------


def test_pct_change():
    assert R.pct_change(150, 100) == 50.0
    assert R.pct_change(50, 100) == -50.0
    assert R.pct_change(5, 0) is None
    assert R.pct_change(0, 0) is None
    assert R.pct_change(5, None) is None


def test_metric_entry():
    assert R.metric_entry(120, 100, True) == {"value": 120, "previous": 100, "change_pct": 20.0}
    assert R.metric_entry(10, None, True) == {"value": 10, "previous": 0, "change_pct": None}
    assert R.metric_entry(10.5, 3, False) == 10.5


# ---- request building ---------------------------------------------------


def test_build_request_defaults_and_cap():
    req = R.build_request(["country"], ["sessions"], date(2026, 3, 1), date(2026, 3, 2), limit=99999)
    assert req["limit"] == R.HARD_ROW_CAP
    assert req["date_ranges"] == [{"start_date": "2026-03-01", "end_date": "2026-03-02"}]
    assert req["order_bys"] == [{"field": "sessions", "kind": "metric", "desc": True}]


def test_order_by_forms():
    assert R.parse_order_by("-sessions", ["country"], ["sessions"])[0]["desc"] is True
    assert R.parse_order_by("country asc", ["country"], ["sessions"]) == [
        {"field": "country", "kind": "dimension", "desc": False}
    ]
    assert R.parse_order_by(None, ["date"], ["sessions"])[0] == {
        "field": "date", "kind": "dimension", "desc": False
    }
    with pytest.raises(ToolError, match="must be one of"):
        R.parse_order_by("revenue", ["country"], ["sessions"])


def test_normalize_filter():
    assert R.normalize_filter(None) is None
    one = R.normalize_filter({"field": "country", "value": "Thailand"})
    assert one == {"and": [{"field": "country", "match": "exact", "value": "Thailand"}]}
    two = R.normalize_filter(
        [{"field": "a", "match": "contains", "value": "x"}, {"field": "b", "match": "REGEX", "value": "^y"}]
    )
    assert [i["match"] for i in two["and"]] == ["contains", "regex"]
    with pytest.raises(ToolError):
        R.normalize_filter({"field": "a"})
    with pytest.raises(ToolError, match="Unsupported"):
        R.normalize_filter({"field": "a", "match": "like", "value": "x"})


# ---- validation ---------------------------------------------------------


def test_validate_fields_suggests_close_matches():
    avail = {"sessionSource", "sessionMedium", "sessionDefaultChannelGroup", "country"}
    errs = R.validate_fields(["sesionSource", "country", "channel"], avail, "dimension")
    assert len(errs) == 2
    assert "sessionSource" in errs[0]
    assert "sessionDefaultChannelGroup" in errs[1]  # substring hint
    assert R.validate_fields(["COUNTRY"], avail, "dimension") == [
        "Unknown dimension 'COUNTRY'. Did you mean: country?"
    ]
    assert "Unknown metric 'zzzzzz'." in R.validate_fields(["zzzzzz"], avail, "metric")[0]


# ---- shaping ------------------------------------------------------------


def test_shape_rows_with_compare():
    cur = data(["sessionDefaultChannelGroup"], ["sessions", "engagementRate"],
               [(["Direct"], [200, 0.5]), (["Organic"], [100, 0.25]), (["New"], [10, 0.1])])
    prev = data(["sessionDefaultChannelGroup"], ["sessions", "engagementRate"],
                [(["Organic"], [200, 0.5]), (["Direct"], [100, 0.5])])
    rows, truncated = R.shape_rows(cur, prev)
    assert truncated is False
    assert rows[0] == {
        "sessionDefaultChannelGroup": "Direct",
        "sessions": {"value": 200, "previous": 100, "change_pct": 100.0},
        "engagementRate": {"value": 0.5, "previous": 0.5, "change_pct": 0.0},
    }
    assert rows[1]["sessions"]["change_pct"] == -50.0
    assert rows[2]["sessions"] == {"value": 10, "previous": 0, "change_pct": None}


def test_shape_rows_no_compare_is_plain_numbers_and_formats_dates():
    cur = data(["date"], ["sessions"], [(["20260301"], [5])])
    rows, _ = R.shape_rows(cur)
    assert rows == [{"date": "2026-03-01", "sessions": 5}]
    assert R.format_dimension("yearMonth", "202603") == "2026-03"
    assert R.format_dimension("isoYearIsoWeek", "202610") == "2026-W10"


def test_truncation_flag_when_ga_has_more_rows():
    cur = data(["country"], ["sessions"], [(["TH"], [1]), (["US"], [1])], row_count=57)
    rows, truncated = R.shape_rows(cur)
    assert truncated and len(rows) == 2
    capped, trunc = R.shape_rows(cur, cap=1)
    assert trunc and len(capped) == 1
    meta = R.build_meta([cur], row_count=2, truncated=True, currency=None, total_rows=57)
    assert meta["truncated"] is True
    assert any("2 of 57" in n for n in meta["notes"])


def test_shape_totals_single_row_and_aggregated():
    cur = data([], ["sessions", "keyEvents"], [([], [100, 10])])
    prev = data([], ["sessions", "keyEvents"], [])  # no data last period
    out = R.shape_totals(cur, prev)
    assert out["sessions"] == {"value": 100, "previous": 0, "change_pct": None}
    agg = data(["x"], ["sessions"], [(["a"], [1])], totals=(40,))
    assert R.shape_totals(agg) == {"sessions": 40}


def test_share_of_sessions_uses_totals_when_present():
    cur = data(["c"], ["sessions"], [(["a"], [30]), (["b"], [10])], totals=(100,))
    rows, _ = R.shape_rows(cur)
    R.add_share(rows, cur)
    assert [r["share_of_sessions"] for r in rows] == [0.3, 0.1]
    no_totals = data(["c"], ["sessions"], [(["a"], [30]), (["b"], [10])])
    rows, _ = R.shape_rows(no_totals)
    R.add_share(rows, no_totals)
    assert rows[0]["share_of_sessions"] == 0.75


def test_meta_flags_and_quota():
    a = data([], ["m"], [], sampled=True, cached=True,
             quota={"tokens_per_day": {"consumed": 9000, "remaining": 1000}})
    b = data([], ["m"], [], thresholded=True, cached=False, currency="THB",
             quota={"tokens_per_day": {"consumed": 100, "remaining": 199900}})
    meta = R.build_meta([a, b], row_count=0, truncated=False, currency=None)
    assert meta["sampled"] and meta["thresholded"]
    assert meta["cached"] is False
    assert meta["currency"] == "THB"
    assert meta["quota"] == {"tokens_per_day": {"remaining": 1000, "remaining_pct": 10.0}}
    healthy = data([], ["m"], [], quota={"tokens_per_day": {"consumed": 1, "remaining": 99}})
    assert "quota" not in R.build_meta([healthy], row_count=0, truncated=False, currency=None)


def test_filter_metadata():
    items = [
        {"api_name": "sessionSource", "ui_name": "Session source", "description": "x"},
        {"api_name": "country", "ui_name": "Country", "description": "Where the user is"},
    ]
    assert [i["api_name"] for i in R.filter_metadata(items, "SOURCE")] == ["sessionSource"]
    assert [i["api_name"] for i in R.filter_metadata(items, "where")] == ["country"]
    assert len(R.filter_metadata(items, None)) == 2


# ---- config parsing (alias resolution) ---------------------------------


def test_alias_resolution():
    reg = parse_properties(
        {
            "default": "main",
            "properties": {
                "main": {"id": 123, "name": "Site", "timezone": "Asia/Bangkok", "key_events": ["purchase"]},
                "app": {"id": "987"},
            },
        }
    )
    assert reg.resolve(None).id == "123"
    assert reg.resolve("app").alias == "app"
    assert reg.resolve("987").alias == "app"  # numeric id of a configured property
    adhoc = reg.resolve("555")
    assert (adhoc.id, adhoc.alias) == ("555", "555")
    assert reg.resolve("properties/555").id == "555"
    with pytest.raises(ToolError, match="Unknown property"):
        reg.resolve("nope")


def test_registry_errors():
    with pytest.raises(ToolError, match="No default"):
        parse_properties({"properties": {"a": {"id": "1"}, "b": {"id": "2"}}}).resolve(None)
    assert parse_properties({"properties": {"a": {"id": "1"}}}).resolve(None).alias == "a"
    with pytest.raises(ValueError, match="default"):
        parse_properties({"default": "x", "properties": {"a": {"id": "1"}}})
    with pytest.raises(ValueError, match="timezone"):
        parse_properties({"properties": {"a": {"id": "1", "timezone": "Mars/Base"}}})
