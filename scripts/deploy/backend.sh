#!/usr/bin/env bash
# Deploy converse-backend to Cloud Run.  ./scripts/deploy/backend.sh <tag>
# Build & push europe-west2-docker.pkg.dev/converse-2997/converse/backend:<tag> first.
set -euo pipefail

tag="${1:?usage: backend.sh <image-tag> (e.g. v3)}"
here="$(cd "$(dirname "$0")" && pwd)"

gcloud run deploy converse-backend --flags-file="$here/backend.yaml" \
  --image "europe-west2-docker.pkg.dev/converse-2997/converse/backend:$tag"

gcloud run services describe converse-backend --region europe-west2 --format='value(status.url)'
