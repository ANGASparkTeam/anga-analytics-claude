"""Authentication for the GA4 marketing MCP server.

Users sign in with Google through FastMCP's OAuth proxy (``GoogleProvider``),
which gives MCP clients (claude.ai, Claude Desktop) Dynamic Client Registration
and issues its own FastMCP JWTs. GA4 data is read with the Cloud Run service
account, so we only ask users for ``openid`` + ``userinfo.email``.

Domain restriction is enforced in three places so a non-company account never
holds a working MCP token:

1. **IdP callback** (``_handle_idp_callback``): right after Google returns, the
   upstream token is verified and the identity checked. A denied user gets a
   clear 403 page and the one-time authorization code is destroyed, so no
   FastMCP token is ever minted.
2. **Code exchange** (``exchange_authorization_code``): checked again before
   minting tokens (defense in depth, e.g. if the callback hook ever breaks).
3. **Every MCP request** (``DomainRestrictedGoogleTokenVerifier.verify_token``):
   the OAuth proxy validates the upstream Google token on each request; the
   identity check runs there too, so refreshed tokens are re-checked as well.

The check itself is the pure function :func:`identity_denial_reason`.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import parse_qs, urlsplit

from cryptography.fernet import Fernet, MultiFernet
from fastmcp.server.auth import AuthProvider
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.oauth_proxy.ui import create_error_html
from fastmcp.server.auth.providers.google import GoogleProvider, GoogleTokenVerifier
from key_value.aio.protocols import AsyncKeyValue
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
from mcp.server.auth.provider import AuthorizationCode, TokenError
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

logger = logging.getLogger("ga4_mcp.auth")

USER_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email"]

DEFAULT_CLIENT_REDIRECT_URIS = [
    "https://claude.ai/api/mcp/auth_callback",
    "https://claude.com/api/mcp/auth_callback",
    # Local tools (MCP Inspector, Claude Code) use loopback callbacks.
    "http://localhost:*",
    "http://127.0.0.1:*",
]

_TRUE = {"1", "true", "yes", "on"}


class AuthConfigError(RuntimeError):
    """Raised when required auth configuration is missing or invalid."""


# ---------------------------------------------------------------------------
# Pure identity policy
# ---------------------------------------------------------------------------


def parse_allowed_domains(raw: str | Iterable[str] | None) -> frozenset[str]:
    """Parse ``ALLOWED_DOMAINS`` ("a.com, b.co.th") into a normalised set."""
    if raw is None:
        return frozenset()
    parts = raw.split(",") if isinstance(raw, str) else list(raw)
    domains = set()
    for part in parts:
        d = part.strip().lower().lstrip("@").rstrip(".")
        if d:
            domains.add(d)
    return frozenset(domains)


def parse_denied_emails(*raws: str | None) -> frozenset[str]:
    """Parse comma-separated email lists (``DENIED_EMAILS`` etc.) into a lower-cased set."""
    return frozenset(
        e.strip().lower() for raw in raws if raw for e in raw.split(",") if e.strip()
    )


def _is_true(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


def email_domain(email: Any) -> str | None:
    """Return the lower-cased domain of a syntactically sane email, else None."""
    if not isinstance(email, str):
        return None
    if email.count("@") != 1:
        return None
    local, domain = email.split("@")
    if not local or not domain:
        return None
    # Reject anything that is not plain ASCII (homoglyph / IDN tricks) or has
    # whitespace / control characters.
    if not domain.isascii() or any(c.isspace() or ord(c) < 33 for c in email):
        return None
    return domain.lower()


def identity_denial_reason(
    *,
    email: Any,
    email_verified: Any,
    hd: Any,
    allowed_domains: frozenset[str],
    require_hd: bool = True,
    denied_emails: frozenset[str] = frozenset(),
) -> str | None:
    """Return why an identity is denied, or ``None`` when it is allowed.

    Rules (fail closed):
    - ``allowed_domains`` must be non-empty.
    - email must be present, verified (``True`` / ``"true"``) and its domain
      must *exactly* equal an allowed domain (no suffix/subdomain matching, so
      ``evil-anga.co.th``, ``x.anga.co.th`` and ``anga.co.th.evil.com`` fail).
    - when ``require_hd`` the Google Workspace hosted-domain claim ``hd`` must
      also be an allowed domain (consumer Google accounts have no ``hd``).
    - the email must not be in ``denied_emails`` (e.g. the shared mailbox the
      server reads GA4 as, so every request is attributable to a person).
    """
    if not allowed_domains:
        return "server misconfigured: ALLOWED_DOMAINS is empty"
    domain = email_domain(email)
    if domain is None:
        return "missing or invalid email"
    if not _is_true(email_verified):
        return "email not verified"
    if domain not in allowed_domains:
        return f"email domain '{domain}' is not allowed"
    if email.lower() in denied_emails:
        return "shared/service mailbox may not sign in; use a personal work account"
    if require_hd:
        hd_norm = hd.strip().lower() if isinstance(hd, str) else ""
        if not hd_norm:
            return "not a Google Workspace account (missing hd claim)"
        if hd_norm not in allowed_domains:
            return f"Workspace domain '{hd_norm}' is not allowed"
    return None


def claims_denial_reason(
    claims: Mapping[str, Any] | None,
    allowed_domains: frozenset[str],
    require_hd: bool = True,
    denied_emails: frozenset[str] = frozenset(),
) -> str | None:
    """Apply :func:`identity_denial_reason` to GoogleTokenVerifier claims."""
    claims = claims or {}
    user = claims.get("google_user_data") or {}
    return identity_denial_reason(
        email=claims.get("email"),
        email_verified=claims.get("email_verified"),
        hd=claims.get("hd") or user.get("hd"),
        allowed_domains=allowed_domains,
        require_hd=require_hd,
        denied_emails=denied_emails,
    )


# ---------------------------------------------------------------------------
# FastMCP integration
# ---------------------------------------------------------------------------


class DomainRestrictedGoogleTokenVerifier(GoogleTokenVerifier):
    """Google token verifier that also enforces the Workspace domain policy."""

    def __init__(
        self,
        *,
        allowed_domains: frozenset[str],
        require_hd: bool = True,
        denied_emails: frozenset[str] = frozenset(),
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.allowed_domains = allowed_domains
        self.require_hd = require_hd
        self.denied_emails = denied_emails

    def denial_reason(self, token: AccessToken) -> str | None:
        return claims_denial_reason(
            token.claims, self.allowed_domains, self.require_hd, self.denied_emails
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        result = await super().verify_token(token)
        if result is None:
            return None
        reason = self.denial_reason(result)
        if reason:
            logger.warning(
                "auth denied email=%s reason=%s",
                (result.claims or {}).get("email"),
                reason,
            )
            return None
        return result


class DomainRestrictedGoogleProvider(GoogleProvider):
    """GoogleProvider that refuses to mint tokens for non-allowed identities."""

    def __init__(
        self,
        *,
        allowed_domains: frozenset[str],
        require_hd: bool = True,
        denied_emails: frozenset[str] = frozenset(),
        cache_ttl_seconds: int | None = 300,
        timeout_seconds: int = 10,
        **kwargs: Any,
    ) -> None:
        if not allowed_domains:
            raise AuthConfigError("ALLOWED_DOMAINS must list at least one domain")
        super().__init__(
            cache_ttl_seconds=cache_ttl_seconds,
            timeout_seconds=timeout_seconds,
            **kwargs,
        )
        # Swap in the domain-enforcing verifier (same settings as the parent's).
        parent = self._token_validator
        self._token_validator = DomainRestrictedGoogleTokenVerifier(
            allowed_domains=allowed_domains,
            require_hd=require_hd,
            denied_emails=denied_emails,
            required_scopes=parent.required_scopes,
            timeout_seconds=timeout_seconds,
            cache_ttl_seconds=cache_ttl_seconds,
            audience=kwargs["client_id"],
        )
        self.allowed_domains = allowed_domains
        self.require_hd = require_hd

    async def _idp_tokens_allowed(self, idp_tokens: Mapping[str, Any]) -> bool:
        access_token = idp_tokens.get("access_token") if idp_tokens else None
        if not access_token:
            return False
        return await self._token_validator.verify_token(access_token) is not None

    async def _handle_idp_callback(
        self, request: Request
    ) -> HTMLResponse | RedirectResponse:
        response = await super()._handle_idp_callback(request)
        if not isinstance(response, RedirectResponse):
            return response
        location = response.headers.get("location", "")
        codes = parse_qs(urlsplit(location).query).get("code")
        if not codes:
            return response  # error redirect back to the client; nothing minted
        code = codes[0]
        code_model = await self._code_store.get(key=code)
        if code_model is not None and await self._idp_tokens_allowed(
            code_model.idp_tokens
        ):
            return response
        await self._code_store.delete(key=code)
        domains = ", ".join(sorted(self.allowed_domains))
        html = create_error_html(
            error_title="Access denied",
            error_message=(
                "This connector is only available to personal company Google "
                f"Workspace accounts ({domains}); shared mailboxes are not allowed. "
                "Sign in again with your own work account."
            ),
        )
        return HTMLResponse(content=html, status_code=403)

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        code_model = await self._code_store.get(key=authorization_code.code)
        if code_model is not None and not await self._idp_tokens_allowed(
            code_model.idp_tokens
        ):
            await self._code_store.delete(key=authorization_code.code)
            raise TokenError("invalid_grant", "Account is not allowed")
        return await super().exchange_authorization_code(client, authorization_code)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def _build_fernet(raw_keys: str) -> MultiFernet:
    keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
    if not keys:
        raise AuthConfigError("STORAGE_ENCRYPTION_KEY is empty")
    try:
        return MultiFernet([Fernet(k.encode()) for k in keys])
    except Exception as e:  # noqa: BLE001
        raise AuthConfigError(
            "STORAGE_ENCRYPTION_KEY must be a Fernet key (generate with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"). '
            "Comma-separate several keys to rotate (first one encrypts)."
        ) from e


def build_client_storage(env: Mapping[str, str]) -> AsyncKeyValue:
    """Build the OAuth proxy's key-value store from ``STORAGE_BACKEND``.

    - ``memory`` (default): lost on restart, single instance only. Local dev.
    - ``file``: FileTree store under ``STORAGE_DIR``. Single host only.
    - ``firestore``: Firestore (Native mode) via ADC. Shared by all Cloud Run
      instances and survives cold starts. Recommended for production.

    Non-memory backends are always wrapped with Fernet encryption
    (``STORAGE_ENCRYPTION_KEY``) because they hold upstream Google tokens.
    """
    backend = env.get("STORAGE_BACKEND", "memory").strip().lower()
    enc = env.get("STORAGE_ENCRYPTION_KEY", "").strip()
    fernet = _build_fernet(enc) if enc else None
    if fernet is None and backend in {"file", "firestore"}:
        raise AuthConfigError(
            f"STORAGE_ENCRYPTION_KEY is required for STORAGE_BACKEND={backend}"
        )

    store: AsyncKeyValue
    if backend == "memory":
        from key_value.aio.stores.memory import MemoryStore

        store = MemoryStore()
    elif backend == "file":
        from pathlib import Path

        from key_value.aio.stores.filetree import (
            FileTreeStore,
            FileTreeV1CollectionSanitizationStrategy,
            FileTreeV1KeySanitizationStrategy,
        )

        directory = Path(env.get("STORAGE_DIR", ".oauth-storage")).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        store = FileTreeStore(
            data_directory=directory,
            key_sanitization_strategy=FileTreeV1KeySanitizationStrategy(directory),
            collection_sanitization_strategy=FileTreeV1CollectionSanitizationStrategy(
                directory
            ),
        )
    elif backend == "firestore":
        from key_value.aio.stores.firestore import (
            FirestoreStore,
            FirestoreV1CollectionSanitizationStrategy,
            FirestoreV1KeySanitizationStrategy,
        )
        from key_value.aio.wrappers.prefix_collections import PrefixCollectionsWrapper

        store = FirestoreStore(
            project=env.get("FIRESTORE_PROJECT") or env.get("GOOGLE_CLOUD_PROJECT") or None,
            database=env.get("FIRESTORE_DATABASE") or None,
            key_sanitization_strategy=FirestoreV1KeySanitizationStrategy(),
            collection_sanitization_strategy=FirestoreV1CollectionSanitizationStrategy(),
        )
        store = PrefixCollectionsWrapper(
            key_value=store,
            prefix=env.get("FIRESTORE_COLLECTION_PREFIX", "ga4mcp"),
        )
    else:
        raise AuthConfigError(
            f"Unknown STORAGE_BACKEND '{backend}' (use memory | file | firestore)"
        )

    if fernet is None:
        return store
    # raise_on_decryption_error=False: entries written with a removed key are
    # treated as missing (user simply re-authenticates) instead of 500s.
    return FernetEncryptionWrapper(
        key_value=store, fernet=fernet, raise_on_decryption_error=False
    )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _env_bool(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in _TRUE


def _require(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise AuthConfigError(f"{name} is required when auth is enabled")
    return value


def on_cloud_run(env: Mapping[str, str]) -> bool:
    return bool(env.get("K_SERVICE"))


def build_auth(env: Mapping[str, str] | None = None) -> AuthProvider | None:
    """Create the auth provider from environment variables.

    Returns ``None`` when ``AUTH_DISABLED=true`` (local development only; this
    is refused on Cloud Run where ``K_SERVICE`` is set).
    """
    env = os.environ if env is None else env

    if _env_bool(env, "AUTH_DISABLED"):
        if on_cloud_run(env):
            raise AuthConfigError("AUTH_DISABLED=true is not allowed on Cloud Run")
        logger.warning("AUTH_DISABLED=true: MCP endpoint is UNAUTHENTICATED (local dev only)")
        return None

    allowed_domains = parse_allowed_domains(_require(env, "ALLOWED_DOMAINS"))
    if not allowed_domains:
        raise AuthConfigError("ALLOWED_DOMAINS must list at least one domain")

    backend = env.get("STORAGE_BACKEND", "memory").strip().lower()
    jwt_signing_key = env.get("JWT_SIGNING_KEY", "").strip() or None
    if jwt_signing_key is None and (backend != "memory" or on_cloud_run(env)):
        raise AuthConfigError(
            "JWT_SIGNING_KEY is required for persistent storage / Cloud Run "
            "(tokens must survive restarts and work across instances)"
        )
    if on_cloud_run(env) and backend == "memory":
        logger.warning(
            "STORAGE_BACKEND=memory on Cloud Run: users will have to reconnect "
            "after every cold start and may fail across instances"
        )

    redirect_uris_raw = env.get("ALLOWED_CLIENT_REDIRECT_URIS", "").strip()
    redirect_uris = (
        [u.strip() for u in redirect_uris_raw.split(",") if u.strip()]
        if redirect_uris_raw
        else list(DEFAULT_CLIENT_REDIRECT_URIS)
    )

    extra_authorize_params: dict[str, str] = {
        # Refresh token needs prompt=consent; select_account lets users with
        # several Google accounts pick the work one.
        "access_type": "offline",
        "prompt": "consent select_account",
    }
    if len(allowed_domains) == 1:
        # UI hint only (Google pre-filters accounts); NOT a security control.
        extra_authorize_params["hd"] = next(iter(allowed_domains))

    return DomainRestrictedGoogleProvider(
        client_id=_require(env, "GOOGLE_OAUTH_CLIENT_ID"),
        client_secret=_require(env, "GOOGLE_OAUTH_CLIENT_SECRET"),
        base_url=_require(env, "BASE_URL").rstrip("/"),
        required_scopes=list(USER_SCOPES),
        allowed_domains=allowed_domains,
        require_hd=_env_bool(env, "REQUIRE_WORKSPACE_HD", default=True),
        # The mailbox GA4 is read as must never be a connector user itself.
        denied_emails=parse_denied_emails(
            env.get("DENIED_EMAILS"), env.get("GA_DELEGATED_SUBJECT")
        ),
        jwt_signing_key=jwt_signing_key,
        client_storage=build_client_storage(env),
        allowed_client_redirect_uris=redirect_uris,
        extra_authorize_params=extra_authorize_params,
    )


def user_email_from_token(token: AccessToken | None) -> str | None:
    """Best-effort email of the caller for audit logging."""
    if token is None:
        return None
    claims = token.claims or {}
    email = claims.get("email")
    if not email:
        upstream = claims.get("upstream_claims") or {}
        email = upstream.get("email") if isinstance(upstream, Mapping) else None
    return email if isinstance(email, str) else None
