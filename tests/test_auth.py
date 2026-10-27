"""Tests for ga4_mcp.auth (domain restriction, storage, factory) and server wiring."""

from __future__ import annotations

import importlib
import sys
import time
import types

import pytest
from cryptography.fernet import Fernet
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.oauth_proxy.models import ClientCode
from fastmcp.server.auth.oauth_proxy.proxy import OAuthProxy
from fastmcp.server.auth.providers.google import GoogleTokenVerifier
from mcp.server.auth.provider import AuthorizationCode, TokenError
from mcp.shared.auth import OAuthClientInformationFull
from starlette.responses import HTMLResponse, RedirectResponse

from ga4_mcp import auth
from ga4_mcp.auth import (
    AuthConfigError,
    DomainRestrictedGoogleProvider,
    DomainRestrictedGoogleTokenVerifier,
    build_auth,
    build_client_storage,
    claims_denial_reason,
    identity_denial_reason,
    parse_allowed_domains,
    parse_denied_emails,
    user_email_from_token,
)

ALLOWED = frozenset({"anga.co.th"})


# ---------------------------------------------------------------------------
# Pure policy
# ---------------------------------------------------------------------------


def deny(email, verified=True, hd="anga.co.th", domains=ALLOWED, require_hd=True):
    return identity_denial_reason(
        email=email,
        email_verified=verified,
        hd=hd,
        allowed_domains=domains,
        require_hd=require_hd,
    )


@pytest.mark.parametrize(
    "email,verified,hd",
    [
        ("alice@anga.co.th", True, "anga.co.th"),
        ("alice@anga.co.th", "true", "anga.co.th"),
        ("Alice@ANGA.CO.TH", "TRUE", "Anga.Co.Th"),
    ],
)
def test_allowed_identities(email, verified, hd):
    assert deny(email, verified, hd) is None


@pytest.mark.parametrize(
    "email",
    [
        "bob@gmail.com",
        "bob@other.com",
        "bob@evil-anga.co.th",
        "bob@xanga.co.th",
        "bob@anga.co.th.evil.com",
        "bob@sub.anga.co.th",
        "bob@anga.co",
        "bob@anga.co.th.",
        "anga.co.th@evil.com",
        "bob@evil.com@anga.co.th",
        "bob@anga.co.th@evil.com",
        "@anga.co.th",
        "bob@",
        "bob",
        "bob@anga.co.th\n",
        "bob @anga.co.th",
        "bob@аnga.co.th",  # Cyrillic 'а' homoglyph
        "",
        None,
        123,
    ],
)
def test_denied_emails(email):
    assert deny(email) is not None


@pytest.mark.parametrize("verified", [False, "false", "False", None, "", 0, 1, "yes"])
def test_unverified_email_denied(verified):
    assert deny("alice@anga.co.th", verified=verified) == "email not verified"


@pytest.mark.parametrize("hd", [None, "", "gmail.com", "evil-anga.co.th", "sub.anga.co.th"])
def test_hd_required_and_must_match(hd):
    assert deny("alice@anga.co.th", hd=hd) is not None


def test_hd_optional_when_disabled():
    assert deny("alice@anga.co.th", hd=None, require_hd=False) is None
    # Domain check still applies without hd.
    assert deny("bob@gmail.com", hd=None, require_hd=False) is not None


def test_empty_allowed_domains_denies_everyone():
    assert deny("alice@anga.co.th", domains=frozenset()) is not None


def test_multiple_domains_and_secondary_hd():
    domains = parse_allowed_domains("anga.co.th, Anga-Group.com ")
    assert domains == {"anga.co.th", "anga-group.com"}
    assert deny("x@anga-group.com", hd="anga.co.th", domains=domains) is None
    assert deny("x@anga-group.com", hd="other.com", domains=domains) is not None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("anga.co.th", {"anga.co.th"}),
        (" @ANGA.co.th. , ,b.com", {"anga.co.th", "b.com"}),
        ("", set()),
        (None, set()),
        (["A.com", " "], {"a.com"}),
    ],
)
def test_parse_allowed_domains(raw, expected):
    assert parse_allowed_domains(raw) == expected


def test_claims_denial_reason_uses_userinfo_hd():
    claims = {
        "email": "alice@anga.co.th",
        "email_verified": "true",
        "google_user_data": {"hd": "anga.co.th"},
    }
    assert claims_denial_reason(claims, ALLOWED) is None
    claims["google_user_data"] = {}
    assert claims_denial_reason(claims, ALLOWED) is not None
    assert claims_denial_reason(None, ALLOWED) is not None


SHARED = frozenset({"shared-mailbox@anga.co.th"})


@pytest.mark.parametrize("email", ["shared-mailbox@anga.co.th", "Shared-Mailbox@ANGA.co.th"])
def test_shared_mailbox_denied(email):
    reason = identity_denial_reason(
        email=email, email_verified=True, hd="anga.co.th",
        allowed_domains=ALLOWED, denied_emails=SHARED,
    )  # fmt: skip
    assert reason is not None and "shared" in reason


def test_denied_emails_do_not_affect_colleagues():
    assert identity_denial_reason(
        email="alice@anga.co.th", email_verified=True, hd="anga.co.th",
        allowed_domains=ALLOWED, denied_emails=SHARED,
    ) is None  # fmt: skip


def test_parse_denied_emails_merges_sources():
    assert parse_denied_emails(" A@x.com, ,b@x.com", "Shared-Mailbox@anga.co.th", None, "") == {
        "a@x.com", "b@x.com", "shared-mailbox@anga.co.th",
    }  # fmt: skip


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------


def make_token(email="alice@anga.co.th", verified="true", hd="anga.co.th") -> AccessToken:
    return AccessToken(
        token="upstream-token",
        client_id="sub-1",
        scopes=list(auth.USER_SCOPES),
        expires_at=int(time.time()) + 3600,
        subject="sub-1",
        claims={
            "sub": "sub-1",
            "email": email,
            "email_verified": verified,
            "google_user_data": {"hd": hd} if hd else {"email": email},
        },
    )


@pytest.fixture
def fake_google(monkeypatch):
    """Make GoogleTokenVerifier.verify_token return a configurable token."""
    state: dict = {"token": make_token()}

    async def fake_verify(self, token):
        return state["token"]

    monkeypatch.setattr(GoogleTokenVerifier, "verify_token", fake_verify)
    return state


def make_verifier():
    return DomainRestrictedGoogleTokenVerifier(
        allowed_domains=ALLOWED, required_scopes=list(auth.USER_SCOPES)
    )


@pytest.mark.asyncio
async def test_verifier_allows_company_account(fake_google):
    result = await make_verifier().verify_token("t")
    assert result is not None
    assert user_email_from_token(result) == "alice@anga.co.th"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "token",
    [
        make_token(email="bob@gmail.com", hd=None),
        make_token(email="bob@evil-anga.co.th", hd="evil-anga.co.th"),
        make_token(verified="false"),
        make_token(hd=None),
        make_token(email=None),
    ],
)
async def test_verifier_denies(fake_google, token):
    fake_google["token"] = token
    assert await make_verifier().verify_token("t") is None


@pytest.mark.asyncio
async def test_verifier_passes_through_upstream_failure(fake_google):
    fake_google["token"] = None
    assert await make_verifier().verify_token("t") is None


# ---------------------------------------------------------------------------
# Provider: callback + code exchange
# ---------------------------------------------------------------------------


def base_env(**overrides) -> dict[str, str]:
    env = {
        "ALLOWED_DOMAINS": "anga.co.th",
        "BASE_URL": "https://ga4-mcp.example.run.app/",
        "GOOGLE_OAUTH_CLIENT_ID": "cid.apps.googleusercontent.com",
        "GOOGLE_OAUTH_CLIENT_SECRET": "secret",
        "JWT_SIGNING_KEY": "x" * 48,
        "STORAGE_BACKEND": "memory",
    }
    env.update(overrides)
    return env


@pytest.fixture
def provider() -> DomainRestrictedGoogleProvider:
    p = build_auth(base_env())
    assert isinstance(p, DomainRestrictedGoogleProvider)
    p.set_mcp_path("/mcp")
    return p


async def put_code(provider, code="client-code-1"):
    await provider._code_store.put(
        key=code,
        value=ClientCode(
            code=code,
            client_id="client-1",
            redirect_uri="https://claude.ai/api/mcp/auth_callback",
            code_challenge="challenge",
            code_challenge_method="S256",
            scopes=list(auth.USER_SCOPES),
            idp_tokens={
                "access_token": "upstream-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": " ".join(auth.USER_SCOPES),
            },
            expires_at=time.time() + 300,
            created_at=time.time(),
        ),
        ttl=300,
    )
    return code


@pytest.fixture
def fake_parent_callback(monkeypatch):
    """Simulate the parent callback having stored a code and redirecting."""

    async def fake(self, request):
        return RedirectResponse(
            "https://claude.ai/api/mcp/auth_callback?code=client-code-1&state=s",
            status_code=302,
        )

    monkeypatch.setattr(OAuthProxy, "_handle_idp_callback", fake)


@pytest.mark.asyncio
async def test_callback_allows_company_account(provider, fake_google, fake_parent_callback):
    await put_code(provider)
    resp = await provider._handle_idp_callback(None)
    assert isinstance(resp, RedirectResponse)
    assert await provider._code_store.get(key="client-code-1") is not None


@pytest.mark.asyncio
async def test_callback_denies_and_burns_code(provider, fake_google, fake_parent_callback):
    fake_google["token"] = make_token(email="bob@gmail.com", hd=None)
    await put_code(provider)
    resp = await provider._handle_idp_callback(None)
    assert isinstance(resp, HTMLResponse)
    assert resp.status_code == 403
    assert b"anga.co.th" in resp.body
    assert await provider._code_store.get(key="client-code-1") is None


def exchange_args(code="client-code-1"):
    client = OAuthClientInformationFull(
        client_id="client-1",
        redirect_uris=["https://claude.ai/api/mcp/auth_callback"],
    )
    ac = AuthorizationCode(
        code=code,
        scopes=list(auth.USER_SCOPES),
        expires_at=time.time() + 300,
        client_id="client-1",
        code_challenge="challenge",
        redirect_uri="https://claude.ai/api/mcp/auth_callback",
        redirect_uri_provided_explicitly=True,
    )
    return client, ac


@pytest.mark.asyncio
async def test_exchange_denied_account_gets_no_token(provider, fake_google):
    fake_google["token"] = make_token(email="eve@anga.co.th.evil.com", hd=None)
    await put_code(provider)
    with pytest.raises(TokenError) as exc:
        await provider.exchange_authorization_code(*exchange_args())
    assert exc.value.error == "invalid_grant"
    assert await provider._code_store.get(key="client-code-1") is None


@pytest.mark.asyncio
async def test_exchange_and_request_flow_for_allowed_account(provider, fake_google):
    await put_code(provider)
    tokens = await provider.exchange_authorization_code(*exchange_args())
    assert tokens.access_token
    # Each MCP request re-validates the upstream token + identity.
    loaded = await provider.load_access_token(tokens.access_token)
    assert loaded is not None
    assert user_email_from_token(loaded) == "alice@anga.co.th"
    # If the identity stops passing the policy, the FastMCP token stops working.
    fake_google["token"] = make_token(hd="other.com")
    assert await provider.load_access_token(tokens.access_token) is None


# ---------------------------------------------------------------------------
# Factory / storage
# ---------------------------------------------------------------------------


def test_auth_disabled_returns_none():
    assert build_auth({"AUTH_DISABLED": "true"}) is None


def test_auth_disabled_refused_on_cloud_run():
    with pytest.raises(AuthConfigError):
        build_auth({"AUTH_DISABLED": "true", "K_SERVICE": "ga4-mcp"})


@pytest.mark.parametrize(
    "missing",
    ["ALLOWED_DOMAINS", "BASE_URL", "GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET"],
)
def test_missing_required_env(missing):
    env = base_env()
    env.pop(missing)
    with pytest.raises(AuthConfigError):
        build_auth(env)


def test_blank_allowed_domains_rejected():
    with pytest.raises(AuthConfigError):
        build_auth(base_env(ALLOWED_DOMAINS=" , "))


def test_jwt_key_required_on_cloud_run():
    env = base_env(K_SERVICE="ga4-mcp")
    env.pop("JWT_SIGNING_KEY")
    with pytest.raises(AuthConfigError):
        build_auth(env)


def test_provider_settings(provider):
    assert provider._extra_authorize_params["hd"] == "anga.co.th"
    assert "consent" in provider._extra_authorize_params["prompt"]
    assert set(provider._token_validator.required_scopes) == set(auth.USER_SCOPES)
    assert isinstance(provider._token_validator, DomainRestrictedGoogleTokenVerifier)


def test_no_hd_hint_for_multiple_domains():
    p = build_auth(base_env(ALLOWED_DOMAINS="a.com,b.com"))
    assert "hd" not in p._extra_authorize_params


def test_persistent_backend_requires_encryption_key(tmp_path):
    with pytest.raises(AuthConfigError):
        build_client_storage({"STORAGE_BACKEND": "file", "STORAGE_DIR": str(tmp_path)})
    with pytest.raises(AuthConfigError):
        build_client_storage({"STORAGE_BACKEND": "firestore"})


def test_bad_encryption_key_rejected(tmp_path):
    with pytest.raises(AuthConfigError):
        build_client_storage(
            {
                "STORAGE_BACKEND": "file",
                "STORAGE_DIR": str(tmp_path),
                "STORAGE_ENCRYPTION_KEY": "not-a-fernet-key",
            }
        )


def test_unknown_backend_rejected():
    with pytest.raises(AuthConfigError):
        build_client_storage({"STORAGE_BACKEND": "redis"})


@pytest.mark.asyncio
async def test_file_storage_is_encrypted_and_supports_rotation(tmp_path):
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    env = {"STORAGE_BACKEND": "file", "STORAGE_DIR": str(tmp_path), "STORAGE_ENCRYPTION_KEY": old}
    store = build_client_storage(env)
    await store.put(key="k", value={"secret": "upstream-refresh-token"}, collection="c")
    raw = b"".join(p.read_bytes() for p in tmp_path.rglob("*") if p.is_file())
    assert b"upstream-refresh-token" not in raw
    rotated = build_client_storage({**env, "STORAGE_ENCRYPTION_KEY": f"{new},{old}"})
    assert await rotated.get(key="k", collection="c") == {"secret": "upstream-refresh-token"}
    # Unknown key -> treated as missing (re-auth), not a crash.
    other = build_client_storage({**env, "STORAGE_ENCRYPTION_KEY": new})
    assert await other.get(key="k", collection="c") is None


def test_firestore_backend_builds(monkeypatch):
    import key_value.aio.stores.firestore as fs

    captured = {}

    from key_value.aio.stores.memory import MemoryStore

    class FakeFirestore(MemoryStore):
        def __init__(self, **kwargs):
            captured.update(kwargs)
            super().__init__()

    monkeypatch.setattr(fs, "FirestoreStore", FakeFirestore)
    store = build_client_storage(
        {
            "STORAGE_BACKEND": "firestore",
            "FIRESTORE_PROJECT": "my-proj",
            "STORAGE_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        }
    )
    assert captured["project"] == "my-proj"
    assert type(store).__name__ == "FernetEncryptionWrapper"


# ---------------------------------------------------------------------------
# Server wiring (uses a stub tools module; does not touch tools.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def server_module(monkeypatch):
    stub = types.ModuleType("ga4_mcp.tools")

    def register_tools(mcp):
        @mcp.tool
        def ping() -> str:
            return "pong"

    stub.register_tools = register_tools
    monkeypatch.setitem(sys.modules, "ga4_mcp.tools", stub)
    monkeypatch.delitem(sys.modules, "ga4_mcp.server", raising=False)
    return importlib.import_module("ga4_mcp.server")


@pytest.mark.asyncio
async def test_healthz_public_and_mcp_requires_auth(server_module, monkeypatch):
    import httpx2

    for k, v in base_env().items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    mcp = server_module.create_server()
    app = mcp.http_app(stateless_http=True)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/health")
        assert r.status_code == 200 and r.json() == {"status": "ok"}
        r = await c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert r.status_code == 401
        assert "www-authenticate" in {k.lower() for k in r.headers}
        r = await c.get("/.well-known/oauth-authorization-server")
        assert r.status_code == 200
        assert "registration_endpoint" in r.json()


@pytest.mark.asyncio
async def test_audit_middleware_logs_tool_call(server_module, monkeypatch, caplog):
    from fastmcp import Client

    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.delenv("K_SERVICE", raising=False)
    mcp = server_module.create_server()
    audit = server_module.audit_logger
    audit.addHandler(caplog.handler)
    try:
        async with Client(mcp) as client:
            result = await client.call_tool("ping", {})
        assert result.data == "pong"
    finally:
        audit.removeHandler(caplog.handler)
    rec = [r for r in caplog.records if getattr(r, "audit", None)]
    assert rec and rec[-1].audit["tool"] == "ping"
    assert rec[-1].audit["user"] == "anonymous"
    assert "token" not in rec[-1].getMessage().lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "env",
    [
        {"GA_DELEGATED_SUBJECT": "shared-mailbox@anga.co.th"},
        {"DENIED_EMAILS": "shared-mailbox@anga.co.th"},
    ],
)
async def test_build_auth_blocks_shared_mailbox(fake_google, fake_parent_callback, env):
    provider = build_auth(base_env(**env))
    provider.set_mcp_path("/mcp")
    fake_google["token"] = make_token(email="shared-mailbox@anga.co.th")
    await put_code(provider)
    resp = await provider._handle_idp_callback(None)
    assert isinstance(resp, HTMLResponse) and resp.status_code == 403
    assert b"shared mailboxes" in resp.body

    fake_google["token"] = make_token(email="alice@anga.co.th")
    assert await provider._token_validator.verify_token("t") is not None
