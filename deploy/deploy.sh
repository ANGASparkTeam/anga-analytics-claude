#!/usr/bin/env bash
# Build from source (Cloud Build) and deploy/update the Cloud Run service. Idempotent.
#
#   PROJECT_ID=my-proj \
#   ALLOWED_DOMAINS=anga.co.th \
#   GOOGLE_OAUTH_CLIENT_ID=123-abc.apps.googleusercontent.com \
#   GA_DELEGATED_SUBJECT=analytics@your-domain \
#   ./deploy/deploy.sh
#
# Optional: REGION (asia-southeast1), SERVICE (ga4-mcp), BASE_URL (defaults to the
# deterministic run.app URL), MIN_INSTANCES (0), MAX_INSTANCES (3), MEMORY (512Mi),
# PUBLIC_INVOKER_MODE (allow-unauthenticated | no-invoker-iam-check),
# IMAGE (deploy a prebuilt image instead of building from source; used by cloudbuild.yaml).
set -euo pipefail
cd "$(dirname "$0")/.."
source deploy/config.sh

: "${ALLOWED_DOMAINS:?Set ALLOWED_DOMAINS (comma-separated Workspace domains)}"
: "${GOOGLE_OAUTH_CLIENT_ID:?Set GOOGLE_OAUTH_CLIENT_ID}"
if [[ "${GA_AUTH_MODE}" == "user_token" && -z "${DENIED_EMAILS:-}" ]]; then
  echo "Set DENIED_EMAILS to the shared mailbox whose token GA4 is read with (it must not sign in)." >&2
  exit 1
fi
MIN_INSTANCES="${MIN_INSTANCES:-0}"
MAX_INSTANCES="${MAX_INSTANCES:-3}"
MEMORY="${MEMORY:-512Mi}"
PUBLIC_INVOKER_MODE="${PUBLIC_INVOKER_MODE:-allow-unauthenticated}"

PROJECT_NUMBER="$(gc projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
BASE_URL="${BASE_URL:-https://${SERVICE}-${PROJECT_NUMBER}.${REGION}.run.app}"
BASE_URL="${BASE_URL%/}"

# Env vars via a YAML file: ALLOWED_DOMAINS contains commas, which break --set-env-vars.
ENV_FILE="$(mktemp -t ga4-mcp-env.XXXXXX)"
trap 'rm -f "${ENV_FILE}"' EXIT
cat > "${ENV_FILE}" <<YAML
ALLOWED_DOMAINS: "${ALLOWED_DOMAINS}"
BASE_URL: "${BASE_URL}"
GOOGLE_OAUTH_CLIENT_ID: "${GOOGLE_OAUTH_CLIENT_ID}"
GA4_PROPERTIES_FILE: "/config/properties.yaml"
STORAGE_BACKEND: "firestore"
FIRESTORE_PROJECT: "${PROJECT_ID}"
FIRESTORE_DATABASE: "${FIRESTORE_DATABASE}"
REQUIRE_WORKSPACE_HD: "${REQUIRE_WORKSPACE_HD:-true}"
MCP_STATELESS_HTTP: "true"
LOG_LEVEL: "${LOG_LEVEL:-INFO}"
GA_AUTH_MODE: "${GA_AUTH_MODE}"
GA_DELEGATED_SUBJECT: "${GA_DELEGATED_SUBJECT:-}"
# Shared mailboxes that must not sign in to the connector (GA_DELEGATED_SUBJECT is always added).
DENIED_EMAILS: "${DENIED_EMAILS:-}"
GA_SERVICE_ACCOUNT_EMAIL: "${SA_EMAIL}"
GA_USER_TOKEN_FILE: "/ga/token.json"
YAML

SECRETS="JWT_SIGNING_KEY=${SECRET_JWT}:latest,STORAGE_ENCRYPTION_KEY=${SECRET_STORAGE}:latest,GOOGLE_OAUTH_CLIENT_SECRET=${SECRET_OAUTH}:latest,/config/properties.yaml=${SECRET_PROPERTIES}:latest"
if [[ "${GA_AUTH_MODE}" == "user_token" ]]; then
  SECRETS="${SECRETS},/ga/token.json=${SECRET_GA_USER_TOKEN}:latest"
fi

case "${PUBLIC_INVOKER_MODE}" in
  allow-unauthenticated) INVOKER_FLAG="--allow-unauthenticated" ;;
  # For orgs whose "Domain restricted sharing" policy blocks allUsers:
  no-invoker-iam-check)  INVOKER_FLAG="--no-invoker-iam-check" ;;
  *) echo "PUBLIC_INVOKER_MODE must be allow-unauthenticated or no-invoker-iam-check" >&2; exit 1 ;;
esac

# IMAGE set (Cloud Build trigger): deploy that prebuilt image; otherwise build from source.
if [[ -n "${IMAGE:-}" ]]; then
  SOURCE_FLAGS=(--image "${IMAGE}")
else
  SOURCE_FLAGS=(--source .)
fi

log "Deploying ${SERVICE} to ${REGION} (${BASE_URL})"
# The MCP endpoint is protected by OAuth inside the app; Cloud Run itself must be
# publicly reachable so claude.ai can call it.
gc run deploy "${SERVICE}" \
  "${SOURCE_FLAGS[@]}" \
  --region "${REGION}" \
  --service-account "${SA_EMAIL}" \
  ${INVOKER_FLAG} \
  --port 8080 \
  --cpu 1 \
  --memory "${MEMORY}" \
  --concurrency 40 \
  --timeout 300 \
  --min-instances "${MIN_INSTANCES}" \
  --max-instances "${MAX_INSTANCES}" \
  --cpu-boost \
  --env-vars-file "${ENV_FILE}" \
  --set-secrets "${SECRETS}"

ACTUAL_URL="$(gc run services describe "${SERVICE}" --region "${REGION}" --format='value(status.url)')"

log "Health check"
for attempt in 1 2 3 4 5; do
  curl -fsS "${BASE_URL}/health" && echo && break
  [[ ${attempt} == 5 ]] && { echo "ERROR: ${BASE_URL}/health did not answer" >&2; exit 1; }
  sleep $((attempt * 3))
done

cat <<MSG

Service URL      : ${ACTUAL_URL}
BASE_URL (env)   : ${BASE_URL}
Connector URL    : ${BASE_URL}/mcp          <- paste into claude.ai > Organization settings > Connectors
OAuth redirect   : ${BASE_URL}/auth/callback  <- must be in the Google OAuth client's authorized redirect URIs
MSG
