"""Thin async wrapper over the GA4 Data and Admin APIs with TTL caching.

Clients are created lazily (ADC), so importing this module needs no credentials.
Tools talk to the small interface of `GA4Client`; tests substitute a fake via
`set_client`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import Any

from cachetools import TTLCache
from fastmcp.exceptions import ToolError
from google.api_core import exceptions as gexc
from google.auth import exceptions as auth_exc

from .ga_credentials import build_credentials, describe
from .reports import TTL_METADATA, TTL_REALTIME, MetadataSet, ReportData

log = logging.getLogger(__name__)


def describe_identity(capital: bool = False) -> str:
    try:
        text = describe()
    except ValueError:
        text = "the server's Google identity"
    return text[:1].upper() + text[1:] if capital else text


_QUOTA_FIELDS = (
    "tokens_per_day",
    "tokens_per_hour",
    "concurrent_requests",
    "server_errors_per_project_per_hour",
    "potentially_thresholded_requests_per_hour",
    "tokens_per_project_per_hour",
)


def map_ga_error(exc: Exception, property_id: str | None = None) -> ToolError:
    """Turn a Google API/auth exception into a short, actionable ToolError."""
    where = f" for property {property_id}" if property_id else ""
    detail = getattr(exc, "message", None) or str(exc)
    if isinstance(exc, gexc.ResourceExhausted):
        return ToolError(
            f"GA4 API quota exhausted{where}. Wait a few minutes and retry, or use a "
            "shorter date range, fewer dimensions and a smaller limit. "
            f"(GA says: {detail})"
        )
    if isinstance(exc, gexc.PermissionDenied):
        return ToolError(
            f"Permission denied{where}. {describe_identity(capital=True)} must have at least Viewer "
            "access to this GA4 property, and the Analytics Data/Admin APIs must be enabled "
            f"in the Google Cloud project. (GA says: {detail})"
        )
    if isinstance(exc, gexc.InvalidArgument):
        return ToolError(
            f"GA4 rejected the request{where}: {detail}. Check that the dimensions and "
            "metrics are compatible with each other (use get_metadata to look them up)."
        )
    if isinstance(exc, gexc.NotFound):
        return ToolError(f"GA4 property not found{where}. Check the property id. ({detail})")
    # gRPC reports credential refresh/signing failures as 503 "metadata from plugin".
    plugin_auth_failure = isinstance(exc, gexc.ServiceUnavailable) and (
        "metadata from plugin" in str(exc)
    )
    if plugin_auth_failure or isinstance(
        exc, (auth_exc.DefaultCredentialsError, auth_exc.RefreshError, gexc.Unauthenticated)
    ):
        return ToolError(
            "The server could not authenticate to Google Analytics as "
            f"{describe_identity()}. Contact the administrator. ({detail})"
        )
    if isinstance(exc, (gexc.ServiceUnavailable, gexc.DeadlineExceeded)):
        return ToolError(f"GA4 API is temporarily unavailable{where}; please retry shortly.")
    if isinstance(exc, gexc.GoogleAPICallError):
        return ToolError(f"GA4 API error{where}: {detail}")
    return ToolError(f"Unexpected error talking to GA4{where}: {type(exc).__name__}: {detail}")


def _filter_expression(norm: dict[str, Any] | None):
    from google.analytics.data_v1beta import types as t

    if not norm:
        return None
    match_types = {
        "exact": t.Filter.StringFilter.MatchType.EXACT,
        "contains": t.Filter.StringFilter.MatchType.CONTAINS,
        "begins_with": t.Filter.StringFilter.MatchType.BEGINS_WITH,
        "regex": t.Filter.StringFilter.MatchType.FULL_REGEXP,
    }

    def one(item: dict[str, Any]) -> Any:
        if item["match"] == "in_list":
            flt = t.Filter(
                field_name=item["field"],
                in_list_filter=t.Filter.InListFilter(values=item["value"], case_sensitive=True),
            )
        else:
            flt = t.Filter(
                field_name=item["field"],
                string_filter=t.Filter.StringFilter(
                    match_type=match_types[item["match"]],
                    value=item["value"],
                    case_sensitive=item["match"] in ("exact", "regex"),
                ),
            )
        return t.FilterExpression(filter=flt)

    exprs = [one(i) for i in norm["and"]]
    if len(exprs) == 1:
        return exprs[0]
    return t.FilterExpression(and_group=t.FilterExpressionList(expressions=exprs))


def _order_bys(specs: list[dict[str, Any]]) -> list[Any]:
    from google.analytics.data_v1beta import types as t

    out = []
    for s in specs:
        if s["kind"] == "metric":
            out.append(t.OrderBy(metric=t.OrderBy.MetricOrderBy(metric_name=s["field"]), desc=s["desc"]))
        else:
            out.append(
                t.OrderBy(dimension=t.OrderBy.DimensionOrderBy(dimension_name=s["field"]), desc=s["desc"])
            )
    return out


def _convert_report(resp: Any) -> ReportData:
    """Proto RunReport/RunRealtimeReport response -> ReportData."""
    from google.analytics.data_v1beta import types as t

    int_type = t.MetricType.TYPE_INTEGER
    is_int = [h.type_ == int_type for h in resp.metric_headers]

    def metrics(values: Any) -> tuple[float, ...]:
        return tuple(
            int(float(v.value)) if is_int[i] else float(v.value) for i, v in enumerate(values)
        )

    rows = [
        (tuple(d.value for d in r.dimension_values), metrics(r.metric_values)) for r in resp.rows
    ]
    totals = metrics(resp.totals[0].metric_values) if len(resp.totals) else None
    # RunRealtimeReportResponse has no `metadata` field.
    md = resp.metadata if "metadata" in type(resp).meta.fields else None
    quota = None
    if resp.property_quota:
        quota = {}
        for name in _QUOTA_FIELDS:
            q = getattr(resp.property_quota, name, None)
            if q is not None and (q.consumed or q.remaining):
                quota[name] = {"consumed": q.consumed, "remaining": q.remaining}
    return ReportData(
        dimensions=[h.name for h in resp.dimension_headers],
        metrics=[h.name for h in resp.metric_headers],
        rows=rows,
        row_count=resp.row_count or len(rows),
        totals=totals,
        sampled=bool(md and md.sampling_metadatas),
        thresholded=bool(md and md.subject_to_thresholding),
        other_row=bool(md and md.data_loss_from_other_row),
        currency=(md and md.currency_code) or None,
        quota=quota,
    )


class GA4Client:
    def __init__(self) -> None:
        self._data: Any = None
        self._admin: Any = None
        self._credentials: Any = None
        self._caches: dict[int, TTLCache] = {}

    # -- lazy clients -----------------------------------------------------
    def _creds(self) -> Any:
        if self._credentials is None:
            try:
                self._credentials = build_credentials() or False
            except ValueError as exc:
                raise ToolError(f"GA4 credentials are misconfigured: {exc}") from exc
            except Exception as exc:  # noqa: BLE001
                raise map_ga_error(exc) from exc
        return self._credentials or None

    def _data_client(self) -> Any:
        if self._data is None:
            from google.analytics.data_v1beta import BetaAnalyticsDataAsyncClient

            self._data = BetaAnalyticsDataAsyncClient(credentials=self._creds())
        return self._data

    def _admin_client(self) -> Any:
        if self._admin is None:
            from google.analytics.admin_v1beta import AnalyticsAdminServiceAsyncClient

            self._admin = AnalyticsAdminServiceAsyncClient(credentials=self._creds())
        return self._admin

    # -- cache ------------------------------------------------------------
    def _cache(self, ttl: int) -> TTLCache:
        if ttl not in self._caches:
            self._caches[ttl] = TTLCache(maxsize=512, ttl=ttl)
        return self._caches[ttl]

    @staticmethod
    def _key(kind: str, property_id: str, request: Any) -> str:
        return json.dumps([kind, property_id, request], sort_keys=True, default=str)

    # -- API calls --------------------------------------------------------
    async def run_report(self, property_id: str, request: dict[str, Any], ttl: int) -> ReportData:
        key = self._key("report", property_id, request)
        cache = self._cache(ttl)
        if key in cache:
            return replace(cache[key], cached=True)
        from google.analytics.data_v1beta import types as t

        req = t.RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[t.Dimension(name=n) for n in request["dimensions"]],
            metrics=[t.Metric(name=n) for n in request["metrics"]],
            date_ranges=[t.DateRange(**dr) for dr in request["date_ranges"]],
            dimension_filter=_filter_expression(request.get("dimension_filter")),
            order_bys=_order_bys(request.get("order_bys", [])),
            limit=request["limit"],
            return_property_quota=True,
            metric_aggregations=[t.MetricAggregation.TOTAL] if request.get("totals") else [],
        )
        try:
            resp = await self._data_client().run_report(request=req)
        except Exception as exc:  # noqa: BLE001 - mapped to a ToolError
            raise map_ga_error(exc, property_id) from exc
        data = _convert_report(resp)
        cache[key] = data
        return data

    async def run_realtime_report(self, property_id: str, request: dict[str, Any]) -> ReportData:
        key = self._key("realtime", property_id, request)
        cache = self._cache(TTL_REALTIME)
        if key in cache:
            return replace(cache[key], cached=True)
        from google.analytics.data_v1beta import types as t

        req = t.RunRealtimeReportRequest(
            property=f"properties/{property_id}",
            dimensions=[t.Dimension(name=n) for n in request["dimensions"]],
            metrics=[t.Metric(name=n) for n in request["metrics"]],
            order_bys=_order_bys(request.get("order_bys", [])),
            limit=request["limit"],
            return_property_quota=True,
            metric_aggregations=[t.MetricAggregation.TOTAL] if request.get("totals") else [],
        )
        try:
            resp = await self._data_client().run_realtime_report(request=req)
        except Exception as exc:  # noqa: BLE001
            raise map_ga_error(exc, property_id) from exc
        data = _convert_report(resp)
        cache[key] = data
        return data

    async def get_metadata(self, property_id: str) -> MetadataSet:
        key = self._key("metadata", property_id, None)
        cache = self._cache(TTL_METADATA)
        if key in cache:
            return cache[key]
        try:
            resp = await self._data_client().get_metadata(name=f"properties/{property_id}/metadata")
        except Exception as exc:  # noqa: BLE001
            raise map_ga_error(exc, property_id) from exc
        meta = MetadataSet(
            dimensions=[
                {
                    "api_name": d.api_name,
                    "ui_name": d.ui_name,
                    "description": d.description,
                    "category": d.category,
                    "custom": bool(d.custom_definition),
                }
                for d in resp.dimensions
            ],
            metrics=[
                {
                    "api_name": m.api_name,
                    "ui_name": m.ui_name,
                    "description": m.description,
                    "category": m.category,
                    "custom": bool(m.custom_definition),
                    "type": m.type_.name.removeprefix("TYPE_").lower(),
                }
                for m in resp.metrics
            ],
        )
        cache[key] = meta
        return meta

    async def list_accounts(self) -> list[dict[str, Any]]:
        """Accessible GA accounts/properties via Admin API account summaries."""
        key = self._key("accounts", "-", None)
        cache = self._cache(TTL_METADATA)
        if key in cache:
            return cache[key]
        try:
            pager = await self._admin_client().list_account_summaries()
            accounts = [
                {
                    "account": s.account.removeprefix("accounts/"),
                    "account_name": s.display_name,
                    "properties": [
                        {
                            "property_id": p.property.removeprefix("properties/"),
                            "display_name": p.display_name,
                        }
                        for p in s.property_summaries
                    ],
                }
                async for s in pager
            ]
        except Exception as exc:  # noqa: BLE001
            raise map_ga_error(exc) from exc
        cache[key] = accounts
        return accounts


_client: GA4Client | None = None


def get_client() -> GA4Client:
    global _client
    if _client is None:
        _client = GA4Client()
    return _client


def set_client(client: Any | None) -> None:
    """Install a (fake) client, or None to reset. Used by tests."""
    global _client
    _client = client
