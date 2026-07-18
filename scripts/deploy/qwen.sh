#!/usr/bin/env bash
# Deploy the Qwen3-8B vLLM service to Cloud Run (europe-west1, L4).  ./scripts/deploy/qwen.sh <tag>
# Build & push the image at <tag> first (needs --timeout=3600s, ~20-35min).
set -euo pipefail

tag="${1:?usage: qwen.sh <image-tag> (e.g. v1)}"
here="$(cd "$(dirname "$0")" && pwd)"

gcloud run deploy converse-qwen --flags-file="$here/qwen.yaml" \
  --image "europe-west1-docker.pkg.dev/converse-2997/converse-hosted-llm/qwen3-8b:$tag"

gcloud run services describe converse-qwen --region europe-west1 --format='value(status.url)'
