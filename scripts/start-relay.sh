#!/bin/sh

set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
RELAY_DIR="${PROJECT_DIR}/relay"
SECRETS_DIR="${RELAY_DIR}/.local"
SECRET_FILE="${SECRETS_DIR}/openai-api-key"
KEYCHAIN_SERVICE="convo-maker-openai-api-key"
KEYCHAIN_ACCOUNT="${USER:-convo-maker}"
DEFAULT_HOST="127.0.0.1"
DEFAULT_PORT="8787"

mkdir -p "${SECRETS_DIR}"
chmod 700 "${SECRETS_DIR}"

print_header() {
  echo "Convo Maker local relay"
  echo "Project: ${PROJECT_DIR}"
  echo
}

ensure_node() {
  if ! command -v node >/dev/null 2>&1; then
    echo "Node.js is required but was not found on your PATH."
    exit 1
  fi
}

ensure_port_available() {
  if ! command -v lsof >/dev/null 2>&1; then
    return 0
  fi

  listener_info="$(lsof -nP -iTCP:${DEFAULT_PORT} -sTCP:LISTEN 2>/dev/null || true)"
  if [ -z "${listener_info}" ]; then
    return 0
  fi

  echo "Port ${DEFAULT_PORT} is already in use."
  echo
  echo "${listener_info}"
  echo
  echo "Stop the existing relay first, then run this script again."
  echo "If you want, you can usually stop it with: kill <PID>"
  exit 1
}

load_key_from_keychain() {
  if ! command -v security >/dev/null 2>&1; then
    return 1
  fi

  security find-generic-password \
    -s "${KEYCHAIN_SERVICE}" \
    -a "${KEYCHAIN_ACCOUNT}" \
    -w 2>/dev/null
}

store_key_in_keychain() {
  api_key="$1"

  if ! command -v security >/dev/null 2>&1; then
    return 1
  fi

  security add-generic-password \
    -U \
    -s "${KEYCHAIN_SERVICE}" \
    -a "${KEYCHAIN_ACCOUNT}" \
    -w "${api_key}" >/dev/null
}

load_key_from_file() {
  if [ -f "${SECRET_FILE}" ]; then
    cat "${SECRET_FILE}"
    return 0
  fi

  return 1
}

store_key_in_file() {
  api_key="$1"
  umask 177
  printf "%s" "${api_key}" > "${SECRET_FILE}"
  chmod 600 "${SECRET_FILE}"
}

prompt_for_key() {
  echo "Enter your OpenAI API key. Input is hidden." >&2

  if command -v stty >/dev/null 2>&1; then
    old_stty_settings="$(stty -g 2>/dev/null || true)"
    stty -echo 2>/dev/null || true
  else
    old_stty_settings=""
  fi

  printf "API key: " >&2
  IFS= read -r api_key || true

  if [ -n "${old_stty_settings}" ]; then
    stty "${old_stty_settings}" 2>/dev/null || true
  fi

  echo >&2

  if [ -z "${api_key}" ]; then
    echo "No API key was entered." >&2
    exit 1
  fi

  printf "%s" "${api_key}"
}

get_api_key() {
  api_key=""

  if api_key="$(load_key_from_keychain)"; then
    echo "${api_key}"
    return 0
  fi

  if api_key="$(load_key_from_file)"; then
    echo "${api_key}"
    return 0
  fi

  api_key="$(prompt_for_key)"

  if store_key_in_keychain "${api_key}"; then
    echo "Saved API key to your macOS Keychain for future runs." >&2
    echo "${api_key}"
    return 0
  fi

  store_key_in_file "${api_key}"
  echo "Saved API key to ${SECRET_FILE} with local-only permissions." >&2
  echo "${api_key}"
}

maybe_reset_key() {
  if [ "${1:-}" != "--reset-key" ]; then
    return 0
  fi

  if command -v security >/dev/null 2>&1; then
    security delete-generic-password \
      -s "${KEYCHAIN_SERVICE}" \
      -a "${KEYCHAIN_ACCOUNT}" >/dev/null 2>&1 || true
  fi

  rm -f "${SECRET_FILE}"
  echo "Stored API key removed. Run the script again to re-enter it."
  exit 0
}

print_next_steps() {
  cat <<EOF

Relay is starting for Converse.

Extension settings:
  provider  : OpenAI Chat Completions
  relay url : http://${DEFAULT_HOST}:${DEFAULT_PORT}
  path      : /v1/chat/completions
  model     : gpt-4.1-mini

If you ever want to replace the stored key:
  ./scripts/start-relay.sh --reset-key

Stop the relay with Ctrl+C.
EOF
}

main() {
  maybe_reset_key "${1:-}"
  print_header
  ensure_node
  ensure_port_available

  api_key="$(get_api_key)"

  print_next_steps
  echo

  export OPENAI_API_KEY="${api_key}"
  export CONVO_RELAY_HOST="${DEFAULT_HOST}"
  export CONVO_RELAY_PORT="${DEFAULT_PORT}"

  exec node "${RELAY_DIR}/server.mjs"
}

main "${1:-}"
