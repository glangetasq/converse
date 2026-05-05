#!/bin/sh

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SECRETS_DIR="${PROJECT_DIR}/relay/.local"
SECRET_FILE="${SECRETS_DIR}/openai-api-key"
KEYCHAIN_SERVICE="convo-maker-openai-api-key"
KEYCHAIN_ACCOUNT="${USER:-convo-maker}"

load_key_from_keychain() {
  if ! command -v security >/dev/null 2>&1; then
    return 1
  fi

  security find-generic-password \
    -s "${KEYCHAIN_SERVICE}" \
    -a "${KEYCHAIN_ACCOUNT}" \
    -w 2>/dev/null
}

load_key_from_file() {
  if [ -f "${SECRET_FILE}" ]; then
    cat "${SECRET_FILE}"
    return 0
  fi

  return 1
}

get_api_key() {
  api_key=""

  if api_key="$(load_key_from_keychain)"; then
    printf "%s" "${api_key}"
    return 0
  fi

  if api_key="$(load_key_from_file)"; then
    printf "%s" "${api_key}"
    return 0
  fi

  echo "No stored API key found. Run scripts/start-relay.sh first."
  exit 1
}

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required but was not found on your PATH."
  exit 1
fi

API_KEY="$(get_api_key)"

echo "Checking connectivity to OpenAI..."
echo

curl -i https://api.openai.com/v1/models \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json"
