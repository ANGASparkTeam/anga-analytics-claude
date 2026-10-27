"""Thin async wrapper over the Search Console (webmasters v3) REST API with TTL caching.

Uses the same Google identity as GA4 (see ga_credentials) with the webmasters.readonly
scope. Tools talk to the small interface of `GSCClient`; tests substitute a fake via
`set_client`.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib.parse import quote

import httpx
from cachetools import TTLCache
from fastmcp.exceptions import ToolError
from google.auth import exceptions as auth_exc

from .ga_client import describe_identity
from .ga_credentials import GSC_SCOPES, build_credentials
from .reports import TTL_METADATA

log = logging.getLogger(__name__)

API = "https://www.googleapis.com/webmasters/v3"
TIMEOUT = 60.0


def map_gsc_error(exc: Exception, site: str | None = None) -> ToolError:
    """Turn an HTTP/auth exception from Search Console into a short, actionable ToolError."""
    where = f" for {site}" if site else ""
    if isinstance(exc, (auth_exc.DefaultCredentialsError, auth_exc.RefreshError)):
        return ToolError(
            "The server could not authenticate to Search Console as "
            f"{describe_identity()}. The stored token may lack the webmasters.readonly "
            f"scope; contact the administrator. ({exc})"
        )
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        try:
            detail = exc.response.json()["error"]["message"]
        except Exception:  # noqa: BLE001 - non-JSON error body
            detail = exc.response.text[:300]
        if status == 401:
            return ToolError(
                "The server could not authenticate to Search Console as "
                f"{describe_identity()}. Contact the administrator. ({detail})"
            )
        if status == 403:
            return ToolError(
                f"Permission denied{where}. {describe_identity(capital=True)} must be a user "
                "or owner of this Search Console property (check gsc_list_sites; "
                f"'siteUnverifiedUser' sites cannot be queried). (GSC says: {detail})"
            )
        if status == 404:
            return ToolError(f"Search Console property not found{where}. ({detail})")
        if status == 429:
            return ToolError(
                f"Search Console API quota exhausted{where}. Wait a few minutes and retry, or "
                f"use a shorter date range or a smaller limit. (GSC says: {detail})"
            )
        if status == 400:
            return ToolError(f"Search Console rejected the request{where}: {detail}")
        if status >= 500:
            return ToolError(f"Search Console API is temporarily unavailable{where}; retry shortly.")
        return ToolError(f"Search Console API error {status}{where}: {detail}")
    if isinstance(exc, httpx.TransportError):
        return ToolError(f"Search Console API is temporarily unavailable{where}; retry shortly.")
    return ToolError(
        f"Unexpected error talking to Search Console{where}: {type(exc).__name__}: {exc}"
    )


class GSCClient:
    def __init__(self) -> None:
        self._credentials: Any = None
        self._lock: asyncio.Lock | None = None
        self._caches: dict[int, TTLCache] = {}

    # -- auth -------------------------------------------------------------
    def _creds(self) -> Any:
        if self._credentials is None:
            try:
                creds = build_credentials(scopes=GSC_SCOPES)
                if creds is None:
                    import google.auth

                    creds, _ = google.auth.default(scopes=GSC_SCOPES)
            except ValueError as exc:
                raise ToolError(f"Google credentials are misconfigured: {exc}") from exc
            except Exception as exc:  # noqa: BLE001
                raise map_gsc_error(exc) from exc
            self._credentials = creds
        return self._credentials

    async def _token(self) -> str:
        creds = self._creds()
        if not creds.valid:
            self._lock = self._lock or asyncio.Lock()
            async with self._lock:
                if not creds.valid:
                    from google.auth.transport.requests import Request

                    try:
                        await asyncio.to_thread(creds.refresh, Request())
                    except Exception as exc:  # noqa: BLE001
                        raise map_gsc_error(exc) from exc
        return creds.token

    async def _call(self, method: str, path: str, site: str | None, body: Any = None) -> Any:
        headers = {"Authorization": f"Bearer {await self._token()}"}
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as http:
                resp = await http.request(method, f"{API}{path}", headers=headers, json=body)
                resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - mapped to a ToolError
            raise map_gsc_error(exc, site) from exc
        return resp.json()

    # -- cache ------------------------------------------------------------
    def _cache(self, ttl: int) -> TTLCache:
        if ttl not in self._caches:
            self._caches[ttl] = TTLCache(maxsize=512, ttl=ttl)
        return self._caches[ttl]

    # -- API calls --------------------------------------------------------
    async def list_sites(self) -> list[dict[str, str]]:
        """Search Console properties the shared account can see: [{site_url, permission}]."""
        cache = self._cache(TTL_METADATA)
        if "sites" in cache:
            return cache["sites"]
        data = await self._call("GET", "/sites", None)
        sites = [
            {"site_url": s["siteUrl"], "permission": s["permissionLevel"]}
            for s in data.get("siteEntry", [])
        ]
        cache["sites"] = sites
        return sites

    async def query(
        self, site_url: str, body: dict[str, Any], ttl: int
    ) -> tuple[list[dict[str, Any]], bool]:
        """searchAnalytics.query -> (rows, cached). Rows: {keys, clicks, impressions, ctr, position}."""
        key = json.dumps([site_url, body], sort_keys=True)
        cache = self._cache(ttl)
        if key in cache:
            return cache[key], True
        path = f"/sites/{quote(site_url, safe='')}/searchAnalytics/query"
        data = await self._call("POST", path, site_url, body)
        rows = data.get("rows", [])
        cache[key] = rows
        return rows, False


_client: GSCClient | None = None


def get_client() -> GSCClient:
    global _client
    if _client is None:
        _client = GSCClient()
    return _client


def set_client(client: Any | None) -> None:
    """Install a (fake) client, or None to reset. Used by tests."""
    global _client
    _client = client
