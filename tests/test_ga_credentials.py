import json

import pytest
from fastmcp.exceptions import ToolError

from ga4_mcp import ga_credentials as gc
from ga4_mcp.ga_client import GA4Client


def test_default_mode_uses_adc():
    assert gc.auth_mode({}) == "adc"
    assert gc.build_credentials({}) is None


def test_unknown_mode_rejected():
    with pytest.raises(ValueError, match="GA_AUTH_MODE"):
        gc.auth_mode({"GA_AUTH_MODE": "password"})


def test_user_token_mode(tmp_path):
    token = tmp_path / "token.json"
    token.write_text(json.dumps({
        "type": "authorized_user", "client_id": "cid", "client_secret": "secret",
        "refresh_token": "rt",
    }))  # fmt: skip
    creds = gc.build_credentials({"GA_AUTH_MODE": "user_token", "GA_USER_TOKEN_FILE": str(token)})
    assert creds.refresh_token == "rt"
    assert creds.scopes == gc.GA_SCOPES
    gsc = gc.build_credentials(
        {"GA_AUTH_MODE": "user_token", "GA_USER_TOKEN_FILE": str(token)}, scopes=gc.GSC_SCOPES
    )
    assert gsc.scopes == gc.GSC_SCOPES


def test_user_token_mode_requires_file():
    with pytest.raises(ValueError, match="GA_USER_TOKEN_FILE"):
        gc.build_credentials({"GA_AUTH_MODE": "user_token"})


def test_delegated_mode_impersonates_subject(monkeypatch):
    import google.auth

    monkeypatch.setattr(google.auth, "default", lambda scopes=None: (object(), "proj"))
    creds = gc.build_credentials({
        "GA_AUTH_MODE": "delegated",
        "GA_DELEGATED_SUBJECT": "analytics@example.com",
        "GA_SERVICE_ACCOUNT_EMAIL": "sa@proj.iam.gserviceaccount.com",
    })  # fmt: skip
    assert creds._subject == "analytics@example.com"
    assert creds.service_account_email == "sa@proj.iam.gserviceaccount.com"
    assert creds._scopes == gc.GA_SCOPES


def test_delegated_mode_requires_subject_and_sa():
    with pytest.raises(ValueError, match="GA_DELEGATED_SUBJECT"):
        gc.build_credentials({"GA_AUTH_MODE": "delegated", "GA_DELEGATED_SUBJECT": "a@b.c"})


def test_describe_names_the_mailbox():
    env = {"GA_AUTH_MODE": "delegated", "GA_DELEGATED_SUBJECT": "analytics@example.com"}
    assert "analytics@example.com" in gc.describe(env)


def test_client_reports_misconfiguration_as_tool_error(monkeypatch):
    monkeypatch.setenv("GA_AUTH_MODE", "delegated")
    monkeypatch.delenv("GA_DELEGATED_SUBJECT", raising=False)
    with pytest.raises(ToolError, match="misconfigured"):
        GA4Client()._data_client()


def test_grpc_plugin_failure_is_reported_as_auth_problem():
    from google.api_core import exceptions as gexc

    from ga4_mcp.ga_client import map_ga_error

    exc = gexc.ServiceUnavailable("Getting metadata from plugin failed with error: unauthorized_client")
    assert "could not authenticate" in str(map_ga_error(exc))
    assert "temporarily unavailable" in str(map_ga_error(gexc.ServiceUnavailable("backend down")))
