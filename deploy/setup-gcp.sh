#!/usr/bin/env bash
# One-time (idempotent) GCP setup for the GA4 MCP server.
#
#   PROJECT_ID=my-proj \
#   PROPERTIES_FILE=properties.yaml \
#   GOOGLE_OAUTH_CLIENT_SECRET=GOCSPX-... \   # optional; prompted if the secret does not exist yet
#   GA_DELEGATED_SUBJECT=analytics@your-domain \  # GA_AUTH_MODE=delegated (default)
#   ./deploy/setup-gcp.sh
#
# GA_AUTH_MODE=user_token instead needs GA_USER_TOKEN_FILE=<authorized_user json>.
#
# Safe to re-run: existing resources are kept; generated keys are never rotated;
# the properties secret only gets a new version when the file content changed.
set -euo pipefail
cd "$(dirname "$0")/.."
source deploy/config.sh

PROPERTIES_FILE="${PROPERTIES_FILE:-properties.yaml}"

log "Enabling APIs"
gc services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  firestore.googleapis.com \
  analyticsdata.googleapis.com \
  analyticsadmin.googleapis.com \
  searchconsole.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com

log "Runtime service account ${SA_EMAIL}"
if ! gc iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1; then
  gc iam service-accounts create "${SA_NAME}" \
    --display-name="GA4 MCP runtime (reads GA4, OAuth state in Firestore)"
else
  echo "exists"
fi

log "Firestore database ${FIRESTORE_DATABASE} (${FIRESTORE_LOCATION}, Native mode)"
if ! gc firestore databases describe --database="${FIRESTORE_DATABASE}" >/dev/null 2>&1; then
  gc firestore databases create --database="${FIRESTORE_DATABASE}" \
    --location="${FIRESTORE_LOCATION}" --type=firestore-native
else
  echo "exists"
fi

log "Granting Firestore access (roles/datastore.user) to the runtime SA"
# add-iam-policy-binding is idempotent.
gc projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/datastore.user" \
  --condition=None >/dev/null
echo "ok"

if [[ "${GA_AUTH_MODE}" == "delegated" ]]; then
  log "Letting the runtime SA sign JWTs as itself (domain-wide delegation without a key file)"
  gc iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/iam.serviceAccountTokenCreator" >/dev/null
  echo "ok"
fi

secret_exists() { gc secrets describe "$1" >/dev/null 2>&1; }

create_secret_from_stdin() {  # name  (value on stdin)
  local name="$1"
  if ! secret_exists "${name}"; then
    gc secrets create "${name}" --replication-policy=automatic >/dev/null
  fi
  gc secrets versions add "${name}" --data-file=- >/dev/null
}

ensure_generated_secret() {  # name generator-cmd...
  local name="$1"; shift
  if secret_exists "${name}" && gc secrets versions list "${name}" \
       --filter="state=ENABLED" --limit=1 --format="value(name)" | grep -q .; then
    echo "${name}: exists (not rotated)"
  else
    "$@" | tr -d '\n' | create_secret_from_stdin "${name}"
    echo "${name}: created"
  fi
}

gen_jwt_key() { openssl rand -base64 48; }
# Fernet key = urlsafe base64 of 32 random bytes
gen_fernet_key() { openssl rand -base64 32 | tr '+/' '-_'; }

log "Secrets"
ensure_generated_secret "${SECRET_JWT}" gen_jwt_key
ensure_generated_secret "${SECRET_STORAGE}" gen_fernet_key

if secret_exists "${SECRET_OAUTH}" && [[ -z "${GOOGLE_OAUTH_CLIENT_SECRET:-}" ]]; then
  echo "${SECRET_OAUTH}: exists (set GOOGLE_OAUTH_CLIENT_SECRET to add a new version)"
else
  if [[ -z "${GOOGLE_OAUTH_CLIENT_SECRET:-}" && -t 0 ]]; then
    read -r -s -p "Google OAuth client secret (GOCSPX-..., Enter to skip): " GOOGLE_OAUTH_CLIENT_SECRET; echo
  fi
  if [[ -n "${GOOGLE_OAUTH_CLIENT_SECRET:-}" ]]; then
    printf '%s' "${GOOGLE_OAUTH_CLIENT_SECRET}" | create_secret_from_stdin "${SECRET_OAUTH}"
    echo "${SECRET_OAUTH}: new version added"
  else
    echo "${SECRET_OAUTH}: skipped (create the OAuth client, then re-run with GOOGLE_OAUTH_CLIENT_SECRET=...)"
  fi
fi

if [[ -f "${PROPERTIES_FILE}" ]]; then
  current="$(gc secrets versions access latest --secret="${SECRET_PROPERTIES}" 2>/dev/null || true)"
  if [[ "${current}" == "$(cat "${PROPERTIES_FILE}")" ]]; then
    echo "${SECRET_PROPERTIES}: unchanged"
  else
    create_secret_from_stdin "${SECRET_PROPERTIES}" < "${PROPERTIES_FILE}"
    echo "${SECRET_PROPERTIES}: new version from ${PROPERTIES_FILE}"
  fi
elif ! secret_exists "${SECRET_PROPERTIES}"; then
  echo "WARNING: ${PROPERTIES_FILE} not found and secret ${SECRET_PROPERTIES} missing." >&2
  echo "         cp properties.example.yaml properties.yaml, edit it, and re-run." >&2
fi

if [[ "${GA_AUTH_MODE}" == "user_token" ]]; then
  if [[ -n "${GA_USER_TOKEN_FILE:-}" ]]; then
    create_secret_from_stdin "${SECRET_GA_USER_TOKEN}" < "${GA_USER_TOKEN_FILE}"
    echo "${SECRET_GA_USER_TOKEN}: new version from ${GA_USER_TOKEN_FILE}"
  elif ! secret_exists "${SECRET_GA_USER_TOKEN}"; then
    echo "WARNING: GA_AUTH_MODE=user_token but GA_USER_TOKEN_FILE is not set and secret" >&2
    echo "         ${SECRET_GA_USER_TOKEN} is missing. See README section 4." >&2
  fi
fi

log "Granting the runtime SA access to its secrets"
for s in "${SECRET_JWT}" "${SECRET_STORAGE}" "${SECRET_OAUTH}" "${SECRET_PROPERTIES}" "${SECRET_GA_USER_TOKEN}"; do
  if secret_exists "${s}"; then
    gc secrets add-iam-policy-binding "${s}" \
      --member="serviceAccount:${SA_EMAIL}" \
      --role="roles/secretmanager.secretAccessor" >/dev/null
    echo "${s}: ok"
  fi
done

PROJECT_NUMBER="$(gc projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
BASE_URL="${BASE_URL:-https://${SERVICE}-${PROJECT_NUMBER}.${REGION}.run.app}"

case "${GA_AUTH_MODE}" in
  delegated)
    SA_CLIENT_ID="$(gc iam service-accounts describe "${SA_EMAIL}" --format='value(oauth2ClientId)')"
    GA_STEP="Workspace super admin: admin.google.com > Security > API controls > Domain-wide delegation
       > Add new: Client ID ${SA_CLIENT_ID}
                  Scope     https://www.googleapis.com/auth/analytics.readonly
     (the server will then read GA4 as ${GA_DELEGATED_SUBJECT})" ;;
  user_token) GA_STEP="Make sure secret ${SECRET_GA_USER_TOKEN} holds the shared mailbox's refresh token (README section 4)." ;;
  adc) GA_STEP="GA4 Admin > Account access management: add ${SA_EMAIL} as Viewer on every GA account." ;;
esac

cat <<MSG

Done. Next steps (manual, see README):
  1. ${GA_STEP}
  2. Google OAuth client (Web application) authorized redirect URI:
       ${BASE_URL}/auth/callback
  3. ALLOWED_DOMAINS=<your-domain> GOOGLE_OAUTH_CLIENT_ID=<id> PROJECT_ID=${PROJECT_ID} \
     GA_AUTH_MODE=${GA_AUTH_MODE} GA_DELEGATED_SUBJECT=${GA_DELEGATED_SUBJECT:-} ./deploy/deploy.sh
MSG
