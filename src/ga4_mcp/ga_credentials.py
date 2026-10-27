"""Google credentials used to call the GA4 and Search Console APIs.

`GA_AUTH_MODE` picks whose GA4 access the server uses:

- ``adc`` (default): the runtime identity itself (Cloud Run service account, or your
  gcloud ADC locally). That identity must be a Viewer in GA4.
- ``delegated``: the service account impersonates a Workspace user
  (``GA_DELEGATED_SUBJECT``, e.g. a shared mailbox) via domain-wide
  delegation. No key file: the JWT is signed through the IAM Credentials API, so the
  service account needs ``roles/iam.serviceAccountTokenCreator`` on itself and a
  Workspace super admin must allow its client id for the analytics.readonly (and, for
  the gsc_* tools, webmasters.readonly) scope.
- ``user_token``: an ``authorized_user`` JSON (refresh token) of the shared mailbox,
  read from ``GA_USER_TOKEN_FILE``. Mint it with both scopes (deploy/mint_ga_token.py)
  so the gsc_* tools work too.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

GA_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
TOKEN_URI = "https://oauth2.googleapis.com/token"
MODES = ("adc", "delegated", "user_token")


def auth_mode(env: Mapping[str, str] = os.environ) -> str:
    mode = env.get("GA_AUTH_MODE", "adc").strip().lower() or "adc"
    if mode not in MODES:
        raise ValueError(f"GA_AUTH_MODE must be one of {', '.join(MODES)}; got {mode!r}")
    return mode


def describe(env: Mapping[str, str] = os.environ) -> str:
    """Human-readable identity used for GA4, for logs and error messages."""
    mode = auth_mode(env)
    if mode == "delegated":
        return f"{env.get('GA_DELEGATED_SUBJECT', '?')} (domain-wide delegation)"
    if mode == "user_token":
        return "the shared Google account in GA_USER_TOKEN_FILE"
    return "the server's service account"


def build_credentials(
    env: Mapping[str, str] = os.environ, scopes: list[str] = GA_SCOPES
) -> Any | None:
    """Credentials for `scopes`, or None to let the client libraries use ADC."""
    mode = auth_mode(env)
    if mode == "adc":
        return None
    if mode == "user_token":
        from google.oauth2.credentials import Credentials as UserCredentials

        path = env.get("GA_USER_TOKEN_FILE", "").strip()
        if not path:
            raise ValueError("GA_AUTH_MODE=user_token requires GA_USER_TOKEN_FILE")
        return UserCredentials.from_authorized_user_file(path, scopes=scopes)

    import google.auth
    from google.auth import iam
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    subject = env.get("GA_DELEGATED_SUBJECT", "").strip()
    sa_email = env.get("GA_SERVICE_ACCOUNT_EMAIL", "").strip()
    if not subject or not sa_email:
        raise ValueError(
            "GA_AUTH_MODE=delegated requires GA_DELEGATED_SUBJECT and GA_SERVICE_ACCOUNT_EMAIL"
        )
    source, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    signer = iam.Signer(Request(), source, sa_email)
    return service_account.Credentials(
        signer, sa_email, TOKEN_URI, scopes=scopes, subject=subject
    )
