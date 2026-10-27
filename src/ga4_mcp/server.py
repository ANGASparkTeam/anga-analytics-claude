"""GA4 marketing MCP server entry point (Streamable HTTP, Cloud Run friendly)."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import Middleware, MiddlewareContext
from starlette.requests import Request
from starlette.responses import JSONResponse

from ga4_mcp import ga_credentials
from ga4_mcp.auth import build_auth, on_cloud_run, user_email_from_token
from ga4_mcp.ratelimit import RegisterRateLimit, limits_from_env
from ga4_mcp.tools import register_tools

logger = logging.getLogger("ga4_mcp")
audit_logger = logging.getLogger("ga4_mcp.audit")

SERVER_NAME = "marketing-analytics"

INSTRUCTIONS = """\
Read-only Google Analytics 4 (GA4) and Google Search Console (GSC) reporting for the \
marketing team.
- The account can see hundreds of client properties: when the user names a \
client or site, call list_properties(search="<name>") and pass the returned \
property_id as `property`; ask if several match.
- Prefer the purpose-built tools (kpi_summary, channel_performance, \
campaign_performance, page_performance, key_event_breakdown, trend, \
realtime_overview) over run_report; use get_metadata to discover valid \
dimension/metric names before calling run_report.
- Dates accept YYYY-MM-DD or GA relative values (today, yesterday, 7daysAgo). \
Rates are fractions 0-1; money is in meta.currency.
- Search Console (organic Google Search keywords, clicks, impressions, CTR, rank): \
find the site with gsc_list_sites(search="<name>") and pass its site_url as `site` to \
gsc_performance, gsc_top_queries, gsc_top_pages and gsc_page_queries. GSC data lags \
2-3 days (default end_date is 3daysAgo); ctr is 0-1; lower position is better.
- Check meta.sampled / meta.thresholded / meta.truncated / meta.notes and \
mention them when they affect conclusions. Never invent numbers.
"""


class _JsonFormatter(logging.Formatter):
    """One JSON object per line so Cloud Logging picks up severity/fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "audit", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    root = logging.getLogger("ga4_mcp")
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    if on_cloud_run(os.environ) or os.environ.get("LOG_FORMAT") == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
    root.addHandler(handler)
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
    root.propagate = False


def _summarise_args(args: dict[str, Any] | None) -> dict[str, Any]:
    """Tool arguments are GA query params (no secrets); keep them short."""
    out: dict[str, Any] = {}
    for key, value in (args or {}).items():
        text = value if isinstance(value, (int, float, bool)) or value is None else str(value)
        if isinstance(text, str) and len(text) > 200:
            text = text[:200] + "..."
        out[key] = text
    return out


class AuditMiddleware(Middleware):
    """Logs who called which tool, how long it took, and whether it failed.

    Only the email from the verified token is logged, never the token itself.
    """

    async def on_call_tool(self, context: MiddlewareContext, call_next):  # type: ignore[override]
        try:
            email = user_email_from_token(get_access_token())
        except Exception:  # noqa: BLE001 - no auth context (AUTH_DISABLED)
            email = None
        tool = getattr(context.message, "name", None)
        args = _summarise_args(getattr(context.message, "arguments", None))
        started = time.perf_counter()
        status = "ok"
        try:
            return await call_next(context)
        except Exception:
            status = "error"
            raise
        finally:
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            audit = {
                "event": "tool_call",
                "user": email or "anonymous",
                "tool": tool,
                "args": args,
                "status": status,
                "elapsed_ms": elapsed_ms,
            }
            audit_logger.info(
                "tool_call user=%s tool=%s status=%s elapsed_ms=%s",
                audit["user"],
                tool,
                status,
                elapsed_ms,
                extra={"audit": audit},
            )


def create_server() -> FastMCP:
    configure_logging()
    mcp = FastMCP(SERVER_NAME, instructions=INSTRUCTIONS, auth=build_auth())
    mcp.add_middleware(AuditMiddleware())

    @mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health(_: Request) -> JSONResponse:  # unauthenticated by design
        return JSONResponse({"status": "ok"})

    register_tools(mcp)
    return mcp


def main() -> None:
    mcp = create_server()
    logging.getLogger(__name__).info("GA4 access as %s", ga_credentials.describe())
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    # Stateless: every request is self-contained, so any Cloud Run instance can
    # serve it (no in-memory MCP session affinity needed).
    stateless = os.environ.get("MCP_STATELESS_HTTP", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    from starlette.middleware import Middleware as ASGIMiddleware

    mcp.run(
        transport="http",
        # /register is public by design (dynamic client registration); cap it.
        middleware=[ASGIMiddleware(RegisterRateLimit, **limits_from_env())],
        host=host,
        port=port,
        stateless_http=stateless,
        show_banner=False,
        uvicorn_config={
            # Cloud Run terminates TLS in front of us.
            "proxy_headers": True,
            "forwarded_allow_ips": "*",
            "timeout_graceful_shutdown": 5,
        },
    )


if __name__ == "__main__":
    main()
