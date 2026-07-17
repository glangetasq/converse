#!/usr/bin/env bash
# Deploy the backend to Cloud Run.  ./scripts/gcp_deploy.sh [tag]
# Build first: gcloud builds submit backend/ --tag "$IMAGE_REPO:<tag>"
set -euo pipefail

SERVICE="converse-backend"
REGION="europe-west2"
IMAGE_REPO="europe-west2-docker.pkg.dev/converse-2997/converse/backend"
FLAGS_FILE="$(dirname "$0")/gcp_deploy_flags_file.yaml"

# a later --image wins over the flags-file
if [ -n "${1:-}" ]; then
  gcloud run deploy "$SERVICE" --flags-file="$FLAGS_FILE" --image "$IMAGE_REPO:$1"
else
  gcloud run deploy "$SERVICE" --flags-file="$FLAGS_FILE"
fi

gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)'
