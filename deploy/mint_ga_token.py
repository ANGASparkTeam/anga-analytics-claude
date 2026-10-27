"""Mint a GA4 + Search Console read-only refresh token for the shared mailbox (GA_AUTH_MODE=user_token).

Requests only analytics.readonly and webmasters.readonly (unlike `gcloud auth application-default login`, which
forces cloud-platform), and writes an `authorized_user` JSON the server can load.

    uv run --with google-auth-oauthlib python deploy/mint_ga_token.py \
        ~/Downloads/client_secret_XXX.json .ga-token.json

Sign in as the shared mailbox in the browser window that opens (set GA_SHARED_ACCOUNT
to pre-fill it). Upload the output with
setup-gcp.sh, then delete it.
"""

import json
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

# openid/email only let us confirm which account was used; GA and GSC access are read-only.
SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email",
          "https://www.googleapis.com/auth/analytics.readonly",
          "https://www.googleapis.com/auth/webmasters.readonly"]


def _email_from_id_token(id_token: str) -> str | None:
    import base64

    payload = id_token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload)).get("email")


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit("usage: mint_ga_token.py <desktop-client-secret.json> <output.json>")
    client_file, out_file = sys.argv[1], sys.argv[2]
    flow = InstalledAppFlow.from_client_secrets_file(client_file, SCOPES)
    creds = flow.run_local_server(
        port=0, prompt="consent", access_type="offline", login_hint=os.environ.get("GA_SHARED_ACCOUNT") or None
    )
    email = (getattr(creds, "id_token", None) and _email_from_id_token(creds.id_token)) or "?"
    print(f"Signed in as: {email}")
    if not creds.refresh_token:
        sys.exit("No refresh token returned; revoke the app's access and try again.")
    fd = os.open(out_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(json.loads(creds.to_json()) | {"type": "authorized_user"}, f)
    print(f"Wrote {out_file} (scopes: {', '.join(creds.scopes or SCOPES)})")


if __name__ == "__main__":
    main()
