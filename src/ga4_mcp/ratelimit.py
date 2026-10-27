"""Rate limit for the open OAuth endpoints (dynamic client registration).

`POST /register` must stay unauthenticated (MCP clients register themselves), so anyone
who finds the URL can call it. Each call stores a client in Firestore; this caps how
fast one address (and one instance overall) can create them. Limits are per Cloud Run
instance, which is enough to stop floods without shared state.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from collections.abc import Mapping

log = logging.getLogger(__name__)

LIMITED_PATHS = ("/register",)


class SlidingWindow:
    def __init__(self, limit: int, window_s: float) -> None:
        self.limit, self.window_s = limit, window_s
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self.window_s:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        if len(self._hits) > 10_000:  # forget idle keys
            for k in [k for k, v in self._hits.items() if not v]:
                del self._hits[k]
        return True


class RegisterRateLimit:
    """ASGI middleware: 429 when one client IP, or the whole instance, registers too often."""

    def __init__(
        self, app, per_ip: int = 10, total: int = 200, window_s: float = 3600.0
    ) -> None:
        self.app = app
        self.per_ip = SlidingWindow(per_ip, window_s)
        self.total = SlidingWindow(total, window_s)

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and scope.get("path", "").rstrip("/") in LIMITED_PATHS
        ):
            ip = (scope.get("client") or ("?", 0))[0]
            if not (self.per_ip.allow(ip) and self.total.allow("*")):
                log.warning("rate limited %s from %s", scope.get("path"), ip)
                body = json.dumps({
                    "error": "too_many_requests",
                    "error_description": "Too many client registrations; try again later.",
                }).encode()  # fmt: skip
                await send({
                    "type": "http.response.start", "status": 429,
                    "headers": [(b"content-type", b"application/json"), (b"retry-after", b"600")],
                })  # fmt: skip
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


def limits_from_env(env: Mapping[str, str] = os.environ) -> dict[str, int]:
    return {
        "per_ip": int(env.get("REGISTER_LIMIT_PER_IP_HOUR", "10")),
        "total": int(env.get("REGISTER_LIMIT_TOTAL_HOUR", "200")),
    }
