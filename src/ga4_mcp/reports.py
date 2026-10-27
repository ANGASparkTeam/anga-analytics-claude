"""Pure helpers: date math, request building, response shaping.

Nothing here touches the network, so everything is unit-testable.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastmcp.exceptions import ToolError

HARD_ROW_CAP = 1000
TTL_HISTORICAL = 15 * 60
TTL_RECENT = 3 * 60
TTL_REALTIME = 60
TTL_METADATA = 60 * 60
LOW_QUOTA_FRACTION = 0.20

COMPARE_MODES = ("previous_period", "previous_year", "none")
MATCH_TYPES = ("exact", "contains", "begins_with", "regex", "in_list")
_TOKEN_QUOTAS = ("tokens_per_day", "tokens_per_hour", "tokens_per_project_per_hour")

_RELATIVE = re.compile(r"^(\d+)daysAgo$")


# --------------------------------------------------------------------------
# Data container returned by the GA client layer
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportData:
    """Normalised GA report response (what ga_client hands to the tools)."""

    dimensions: list[str]
    metrics: list[str]
    rows: list[tuple[tuple[str, ...], tuple[float, ...]]]
    row_count: int  # total matching rows reported by GA (may exceed len(rows))
    totals: tuple[float, ...] | None = None
    sampled: bool = False
    thresholded: bool = False
    other_row: bool = False
    currency: str | None = None
    quota: dict[str, dict[str, int]] | None = None
    cached: bool = False


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------


def today_in(tz: str, now: datetime | None = None) -> date:
    """Today's date in the property's timezone."""
    zone = ZoneInfo(tz)
    return (now.astimezone(zone) if now else datetime.now(zone)).date()


def resolve_date(value: str, today: date) -> date:
    """Resolve YYYY-MM-DD, today, yesterday or NdaysAgo to a concrete date."""
    v = value.strip()
    if v == "today":
        return today
    if v == "yesterday":
        return today - timedelta(days=1)
    m = _RELATIVE.match(v)
    if m:
        return today - timedelta(days=int(m.group(1)))
    try:
        return date.fromisoformat(v)
    except ValueError:
        raise ToolError(
            f"Invalid date '{value}'. Use YYYY-MM-DD (e.g. 2026-03-01), 'today', "
            "'yesterday' or 'NdaysAgo' (e.g. '7daysAgo')."
        ) from None


def resolve_range(start: str, end: str, today: date) -> tuple[date, date]:
    s, e = resolve_date(start, today), resolve_date(end, today)
    if s > e:
        raise ToolError(f"start_date ({s}) is after end_date ({e}).")
    return s, e


def _minus_year(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:  # Feb 29
        return d.replace(year=d.year - 1, day=28)


def compute_compare_range(start: date, end: date, mode: str) -> tuple[date, date] | None:
    """Comparison window for `previous_period` (same length, directly before),
    `previous_year` (same dates one year earlier) or `none`."""
    if mode == "none":
        return None
    if mode == "previous_period":
        days = (end - start).days + 1
        prev_end = start - timedelta(days=1)
        return prev_end - timedelta(days=days - 1), prev_end
    if mode == "previous_year":
        return _minus_year(start), _minus_year(end)
    raise ToolError(f"Invalid compare '{mode}'. Use one of: {', '.join(COMPARE_MODES)}.")


def range_dict(start: date, end: date) -> dict[str, Any]:
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days": (end - start).days + 1,
    }


def cache_ttl(end: date, today: date) -> int:
    """15 min for ranges that ended before today, else 3 min."""
    return TTL_HISTORICAL if end < today else TTL_RECENT


# --------------------------------------------------------------------------
# Request building
# --------------------------------------------------------------------------


def clamp_limit(limit: int | None, default: int = 100) -> int:
    if limit is None:
        return default
    return max(1, min(int(limit), HARD_ROW_CAP))


def normalize_filter(raw: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None) -> dict | None:
    """Simple filter form -> {"and": [{field, match, value}, ...]} (None if empty)."""
    if not raw:
        return None
    if isinstance(raw, Mapping) and "and" in raw:  # already normalised
        return normalize_filter(raw["and"])
    items = [raw] if isinstance(raw, Mapping) else list(raw)
    out = []
    for item in items:
        if not isinstance(item, Mapping) or "field" not in item or "value" not in item:
            raise ToolError(
                "Each dimension_filter needs 'field' and 'value' (and optional 'match': "
                f"{'|'.join(MATCH_TYPES[:4])}). Got: {item!r}"
            )
        match = str(item.get("match") or "exact").lower()
        if match not in MATCH_TYPES:
            raise ToolError(
                f"Unsupported filter match '{match}'. Use one of: {', '.join(MATCH_TYPES[:4])}."
            )
        value = item["value"]
        if match == "in_list":
            value = [str(v) for v in (value if isinstance(value, (list, tuple)) else [value])]
        else:
            value = str(value)
        out.append({"field": str(item["field"]), "match": match, "value": value})
    return {"and": out}


def parse_order_by(
    order_by: str | Sequence[str] | None,
    dimensions: Sequence[str],
    metrics: Sequence[str],
) -> list[dict[str, Any]]:
    """'-sessions' / 'sessions desc' / 'date' -> order spec list.

    Default: date ascending when a `date` dimension is present, else first metric desc.
    """
    if order_by is None or order_by == [] or order_by == "":
        if "date" in dimensions:
            return [{"field": "date", "kind": "dimension", "desc": False}]
        if metrics:
            return [{"field": metrics[0], "kind": "metric", "desc": True}]
        return []
    items = [order_by] if isinstance(order_by, str) else list(order_by)
    out = []
    for item in items:
        s = item.strip()
        desc = False
        if s.startswith("-"):
            desc, s = True, s[1:].strip()
        else:
            m = re.match(r"^(.*?)\s+(asc|desc)$", s, re.IGNORECASE)
            if m:
                s, desc = m.group(1).strip(), m.group(2).lower() == "desc"
        if s in metrics:
            kind = "metric"
        elif s in dimensions:
            kind = "dimension"
        else:
            raise ToolError(
                f"order_by field '{s}' must be one of the requested dimensions or metrics: "
                f"{', '.join([*dimensions, *metrics])}."
            )
        out.append({"field": s, "kind": kind, "desc": desc})
    return out


def build_request(
    dimensions: Sequence[str],
    metrics: Sequence[str],
    start: date,
    end: date,
    *,
    dimension_filter: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    order_by: str | Sequence[str] | None = None,
    limit: int | None = 100,
    totals: bool = False,
) -> dict[str, Any]:
    """Plain-dict report request (JSON-serialisable; doubles as the cache key)."""
    dims, mets = list(dimensions), list(metrics)
    return {
        "dimensions": dims,
        "metrics": mets,
        "date_ranges": [{"start_date": start.isoformat(), "end_date": end.isoformat()}],
        "dimension_filter": normalize_filter(dimension_filter),
        "order_bys": parse_order_by(order_by, dims, mets),
        "limit": clamp_limit(limit),
        "totals": totals,
    }


def build_realtime_request(dimensions: Sequence[str], metrics: Sequence[str], limit: int = 10,
                           totals: bool = False) -> dict[str, Any]:
    return {
        "dimensions": list(dimensions),
        "metrics": list(metrics),
        "dimension_filter": None,
        "order_bys": [{"field": metrics[0], "kind": "metric", "desc": True}],
        "limit": limit,
        "totals": totals,
    }


# --------------------------------------------------------------------------
# Validation against metadata
# --------------------------------------------------------------------------


def suggest(name: str, available: Iterable[str], n: int = 3) -> list[str]:
    pool = list(available)
    lowered = {a.lower(): a for a in pool}
    if name.lower() in lowered:
        return [lowered[name.lower()]]
    close = difflib.get_close_matches(name, pool, n=n, cutoff=0.5)
    if len(close) < n:
        # substring hits help for things like "channel" -> sessionDefaultChannelGroup
        subs = [a for a in pool if name.lower() in a.lower() and a not in close]
        close += subs[: n - len(close)]
    return close


def validate_fields(names: Iterable[str], available: Iterable[str], kind: str) -> list[str]:
    """Error strings (one per unknown name) with close-match suggestions."""
    pool = set(available)
    errors = []
    for name in names:
        if name in pool:
            continue
        hints = suggest(name, pool)
        hint = f" Did you mean: {', '.join(hints)}?" if hints else ""
        errors.append(f"Unknown {kind} '{name}'.{hint}")
    return errors


def raise_if_invalid(errors: Sequence[str]) -> None:
    if errors:
        raise ToolError(
            " ".join(errors) + " Use get_metadata(search=...) to look up valid API names."
        )


# --------------------------------------------------------------------------
# Shaping
# --------------------------------------------------------------------------


def _num(v: float) -> float | int:
    if isinstance(v, int) and not isinstance(v, bool):
        return v
    return int(v) if float(v).is_integer() and abs(v) < 1e15 else round(float(v), 4)


def pct_change(value: float, previous: float | None) -> float | None:
    """Percent change vs previous; None when previous is 0/missing."""
    if not previous:
        return None
    return round((value - previous) / abs(previous) * 100, 2)


def metric_entry(value: float, previous: float | None, compare: bool) -> Any:
    if not compare:
        return _num(value)
    prev = previous or 0
    return {"value": _num(value), "previous": _num(prev), "change_pct": pct_change(value, prev)}


def format_dimension(name: str, value: str) -> str:
    """Make GA's compact date-ish dimension values readable."""
    if name == "date" and re.fullmatch(r"\d{8}", value):
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    if name == "yearMonth" and re.fullmatch(r"\d{6}", value):
        return f"{value[:4]}-{value[4:]}"
    if name == "isoYearIsoWeek" and re.fullmatch(r"\d{6}", value):
        return f"{value[:4]}-W{value[4:]}"
    return value


def shape_rows(
    current: ReportData,
    previous: ReportData | None = None,
    *,
    cap: int = HARD_ROW_CAP,
) -> tuple[list[dict[str, Any]], bool]:
    """Rows as {dim: value, metric: number | {value, previous, change_pct}}.

    Returns (rows, truncated). Rows follow the order of `current`; previous-period
    values are joined on the dimension tuple (missing -> 0).
    """
    compare = previous is not None
    prev_map = {dims: vals for dims, vals in previous.rows} if previous else {}
    shaped = []
    for dims, vals in current.rows[:cap]:
        row: dict[str, Any] = {
            n: format_dimension(n, v) for n, v in zip(current.dimensions, dims, strict=True)
        }
        prev_vals = prev_map.get(dims)
        for i, name in enumerate(current.metrics):
            prev_v = prev_vals[i] if prev_vals else 0
            row[name] = metric_entry(vals[i], prev_v, compare)
        shaped.append(row)
    truncated = current.row_count > len(shaped)
    return shaped, truncated


def shape_totals(current: ReportData, previous: ReportData | None = None) -> dict[str, Any]:
    """Single-row (no dimension) report, or aggregated totals -> {metric: entry}."""
    cur = _totals_vector(current)
    prev = _totals_vector(previous) if previous else None
    compare = previous is not None
    return {
        name: metric_entry(cur[i], prev[i] if prev else None, compare)
        for i, name in enumerate(current.metrics)
    }


def _totals_vector(data: ReportData) -> Sequence[float]:
    if data.totals is not None:
        return data.totals
    if not data.dimensions and data.rows:
        return data.rows[0][1]
    if data.dimensions:
        return [sum(r[1][i] for r in data.rows) for i in range(len(data.metrics))]
    return [0] * len(data.metrics)


def add_share(rows: list[dict[str, Any]], current: ReportData, metric: str = "sessions",
              key: str = "share_of_sessions") -> None:
    """Add `key` (fraction 0-1 of the total `metric`) to each row, in place."""
    if metric not in current.metrics:
        return
    idx = current.metrics.index(metric)
    total = (
        current.totals[idx] if current.totals is not None else sum(r[1][idx] for r in current.rows)
    )
    for row, (_, vals) in zip(rows, current.rows, strict=False):
        row[key] = round(vals[idx] / total, 4) if total else None


def low_quota(quotas: Iterable[dict[str, dict[str, int]] | None]) -> dict[str, Any] | None:
    """Token quotas under 20% remaining (lowest seen across the responses)."""
    low: dict[str, Any] = {}
    for quota in quotas:
        for name in _TOKEN_QUOTAS:
            q = (quota or {}).get(name)
            if not q:
                continue
            total = q.get("consumed", 0) + q.get("remaining", 0)
            if total and q["remaining"] / total < LOW_QUOTA_FRACTION:
                prev = low.get(name)
                if prev is None or q["remaining"] < prev["remaining"]:
                    low[name] = {
                        "remaining": q["remaining"],
                        "remaining_pct": round(q["remaining"] / total * 100, 1),
                    }
    return low or None


def build_meta(
    datas: Sequence[ReportData],
    *,
    row_count: int,
    truncated: bool,
    currency: str | None,
    notes: Iterable[str] = (),
    total_rows: int | None = None,
) -> dict[str, Any]:
    all_notes = list(notes)
    if any(d.sampled for d in datas):
        all_notes.append("Data is sampled by GA4; figures are estimates.")
    if any(d.thresholded for d in datas):
        all_notes.append("GA4 may withhold some rows/values for privacy thresholds.")
    if any(d.other_row for d in datas):
        all_notes.append("Rows beyond the cardinality limit are grouped into '(other)'.")
    if truncated:
        all_notes.append(
            f"Only {row_count} of {total_rows} rows returned; raise limit or add a filter."
        )
    meta: dict[str, Any] = {
        "sampled": any(d.sampled for d in datas),
        "thresholded": any(d.thresholded for d in datas),
        "row_count": row_count,
        "truncated": truncated,
        "cached": bool(datas) and all(d.cached for d in datas),
        "currency": currency or next((d.currency for d in datas if d.currency), None),
        "notes": all_notes,
    }
    if total_rows is not None:
        meta["total_rows"] = total_rows
    quota = low_quota(d.quota for d in datas)
    if quota:
        meta["quota"] = quota
    return meta


def make_response(
    prop: Mapping[str, str] | None,
    date_range: Mapping[str, Any] | None,
    compare_range: Mapping[str, Any] | None,
    meta: Mapping[str, Any],
    **body: Any,
) -> dict[str, Any]:
    return {
        "property": dict(prop) if prop else None,
        "date_range": date_range,
        "compare_range": compare_range,
        **body,
        "meta": dict(meta),
    }


def filter_metadata(items: Sequence[Mapping[str, Any]], search: str | None) -> list[dict]:
    """Substring filter (case-insensitive) over api_name, ui_name and description."""
    if not search:
        return [dict(i) for i in items]
    q = search.lower()
    return [
        dict(i)
        for i in items
        if q in i["api_name"].lower()
        or q in (i.get("ui_name") or "").lower()
        or q in (i.get("description") or "").lower()
    ]


@dataclass
class MetadataSet:
    dimensions: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, Any]] = field(default_factory=list)

    @property
    def dimension_names(self) -> set[str]:
        return {d["api_name"] for d in self.dimensions}

    @property
    def metric_names(self) -> set[str]:
        return {m["api_name"] for m in self.metrics}
