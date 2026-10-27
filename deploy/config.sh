# Shared settings for deploy/setup-gcp.sh and deploy/deploy.sh.
# Override any of these with environment variables, e.g.
#   PROJECT_ID=my-proj ALLOWED_DOMAINS=anga.co.th ./deploy/deploy.sh

: "${PROJECT_ID:?Set PROJECT_ID (GCP project id)}"
REGION="${REGION:-asia-southeast1}"
SERVICE="${SERVICE:-ga4-mcp}"
SA_NAME="${SA_NAME:-${SERVICE}-runtime}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
FIRESTORE_LOCATION="${FIRESTORE_LOCATION:-${REGION}}"
FIRESTORE_DATABASE="${FIRESTORE_DATABASE:-(default)}"

# Secret Manager secret names
SECRET_JWT="${SECRET_JWT:-${SERVICE}-jwt-signing-key}"
SECRET_STORAGE="${SECRET_STORAGE:-${SERVICE}-storage-encryption-key}"
SECRET_OAUTH="${SECRET_OAUTH:-${SERVICE}-google-oauth-client-secret}"
SECRET_PROPERTIES="${SECRET_PROPERTIES:-${SERVICE}-properties}"
SECRET_GA_USER_TOKEN="${SECRET_GA_USER_TOKEN:-${SERVICE}-ga-user-token}"

# Whose GA4 access the server uses (see src/ga4_mcp/ga_credentials.py):
#   delegated  - SA impersonates GA_DELEGATED_SUBJECT via Workspace domain-wide delegation
#   user_token - refresh token of the shared mailbox (Secret Manager)
#   adc        - the SA itself, added as Viewer in GA4
GA_AUTH_MODE="${GA_AUTH_MODE:-user_token}"
case "${GA_AUTH_MODE}" in
  delegated) : "${GA_DELEGATED_SUBJECT:?Set GA_DELEGATED_SUBJECT (e.g. analytics@your-domain)}" ;;
  user_token|adc) ;;
  *) echo "GA_AUTH_MODE must be delegated, user_token or adc" >&2; exit 1 ;;
esac

gc() { gcloud --project "${PROJECT_ID}" --quiet "$@"; }
log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
