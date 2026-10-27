#!/usr/bin/env bash
# One-time (idempotent) setup of the Cloud Build trigger that tests and deploys every
# push to main of the GitHub repo (cloudbuild.yaml). Run it twice on first setup:
#   1st run creates the GitHub connection and prints a link to approve in the browser
#           (authorize Cloud Build and install its GitHub App on the repo's org);
#   2nd run (after approving) links the repo and creates the trigger.
#
#   PROJECT_ID=your-project GITHUB_REPO=owner/repo ALLOWED_DOMAINS=your-domain.com \
#   DENIED_EMAILS=shared@your-domain.com GOOGLE_OAUTH_CLIENT_ID=...apps.googleusercontent.com \
#   ./deploy/setup-cloudbuild.sh
set -euo pipefail
cd "$(dirname "$0")/.."
source deploy/config.sh

: "${GITHUB_REPO:?Set GITHUB_REPO (owner/name)}"
# Deployment-specific values live on the trigger, not in the public cloudbuild.yaml.
: "${ALLOWED_DOMAINS:?Set ALLOWED_DOMAINS (e.g. your-domain.com)}"
: "${DENIED_EMAILS:?Set DENIED_EMAILS (the shared mailbox that must not sign in)}"
: "${GOOGLE_OAUTH_CLIENT_ID:?Set GOOGLE_OAUTH_CLIENT_ID (web client)}"
CONNECTION="${CONNECTION:-github}"
REPO_NAME="${GITHUB_REPO#*/}"
TRIGGER="${TRIGGER:-${SERVICE}-deploy-main}"
DEPLOYER_NAME="${DEPLOYER_NAME:-${SERVICE}-deployer}"
DEPLOYER_EMAIL="${DEPLOYER_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
PROJECT_NUMBER="$(gc projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
BUILD_SA="${BUILD_SA:-${PROJECT_NUMBER}-compute@developer.gserviceaccount.com}"
CB_AGENT="service-${PROJECT_NUMBER}@gcp-sa-cloudbuild.iam.gserviceaccount.com"

bind_project_role() {  # member role  (retries: setIamPolicy races on new projects)
  for attempt in 1 2 3 4 5; do
    gc projects add-iam-policy-binding "${PROJECT_ID}" --member="$1" --role="$2" \
      --condition=None >/dev/null 2>&1 && { echo "$2: ok"; return; }
    sleep $((attempt * 3))
  done
  echo "$2: FAILED" >&2; exit 1
}

log "APIs"
gc services enable cloudbuild.googleapis.com secretmanager.googleapis.com cloudresourcemanager.googleapis.com

log "Deployer service account ${DEPLOYER_EMAIL} (runs the builds)"
if ! gc iam service-accounts describe "${DEPLOYER_EMAIL}" >/dev/null 2>&1; then
  gc iam service-accounts create "${DEPLOYER_NAME}" --display-name="Cloud Build deployer for ${SERVICE}"
fi
for role in roles/run.admin roles/artifactregistry.writer roles/logging.logWriter \
            roles/storage.objectUser roles/browser; do
  bind_project_role "serviceAccount:${DEPLOYER_EMAIL}" "${role}"
done
for sa in "${SA_EMAIL}" "${BUILD_SA}"; do
  gc iam service-accounts add-iam-policy-binding "${sa}" \
    --member="serviceAccount:${DEPLOYER_EMAIL}" --role="roles/iam.serviceAccountUser" >/dev/null
done
echo "actAs runtime SA: ok"

log "Cloud Build service agent may store the GitHub token in Secret Manager"
gc beta services identity create --service=cloudbuild.googleapis.com >/dev/null 2>&1 || true
bind_project_role "serviceAccount:${CB_AGENT}" roles/secretmanager.admin

log "GitHub connection ${CONNECTION} (${REGION})"
if ! gc builds connections describe "${CONNECTION}" --region="${REGION}" >/dev/null 2>&1; then
  gc builds connections create github "${CONNECTION}" --region="${REGION}"
fi
STAGE="$(gc builds connections describe "${CONNECTION}" --region="${REGION}" \
  --format='value(installationState.stage)')"
if [[ "${STAGE}" != "COMPLETE" ]]; then
  ACTION="$(gc builds connections describe "${CONNECTION}" --region="${REGION}" \
    --format='value(installationState.actionUri)')"
  cat <<MSG

Connection is ${STAGE}. Open this link, sign in to GitHub, authorize Cloud Build and
install the Google Cloud Build app on ${GITHUB_REPO%/*} (at least the ${REPO_NAME} repo):
  ${ACTION}
Then re-run this script.
MSG
  exit 0
fi
echo "connection: COMPLETE"

log "Linked repository ${REPO_NAME}"
if ! gc builds repositories describe "${REPO_NAME}" --connection="${CONNECTION}" \
     --region="${REGION}" >/dev/null 2>&1; then
  gc builds repositories create "${REPO_NAME}" --connection="${CONNECTION}" \
    --region="${REGION}" --remote-uri="https://github.com/${GITHUB_REPO}.git"
else
  echo "exists"
fi

log "Trigger ${TRIGGER}: push to main -> cloudbuild.yaml"
if ! gc builds triggers describe "${TRIGGER}" --region="${REGION}" >/dev/null 2>&1; then
  gc builds triggers create github --name="${TRIGGER}" --region="${REGION}" \
    --repository="projects/${PROJECT_ID}/locations/${REGION}/connections/${CONNECTION}/repositories/${REPO_NAME}" \
    --branch-pattern='^main$' --build-config=cloudbuild.yaml \
    --service-account="projects/${PROJECT_ID}/serviceAccounts/${DEPLOYER_EMAIL}" \
    --substitutions="^|^_ALLOWED_DOMAINS=${ALLOWED_DOMAINS}|_DENIED_EMAILS=${DENIED_EMAILS}|_GOOGLE_OAUTH_CLIENT_ID=${GOOGLE_OAUTH_CLIENT_ID}"
else
  echo "exists (update its substitutions in the console or delete it and re-run)"
fi

cat <<MSG

Done. Every push to main now runs tests, builds and deploys ${SERVICE}.
Run it now without a push:
  gcloud builds triggers run ${TRIGGER} --region=${REGION} --branch=main --project=${PROJECT_ID}
MSG
