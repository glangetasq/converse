#!/bin/sh

set -eu

MODEL="${OPENAI_TEST_MODEL:-gpt-4.1-mini}"
API_URL="https://api.openai.com/v1/chat/completions"

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

ensure_dependencies() {
  if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required but was not found on your PATH."
    exit 1
  fi

  if ! command -v node >/dev/null 2>&1; then
    echo "Node.js is required but was not found on your PATH."
    exit 1
  fi
}

main() {
  ensure_dependencies
  API_KEY="$(prompt_for_key)"

  echo "Calling OpenAI with model ${MODEL}..." >&2

  RESPONSE_FILE="$(mktemp)"
  HTTP_STATUS="$(
    curl -sS \
      -o "${RESPONSE_FILE}" \
      -w "%{http_code}" \
      -X POST "${API_URL}" \
      -H "Authorization: Bearer ${API_KEY}" \
      -H "Content-Type: application/json" \
      -d "{
        \"model\": \"${MODEL}\",
        \"messages\": [
          {
            \"role\": \"system\",
            \"content\": \"You are a statistics professor. Return exactly one sentence and no bullet points.\"
          },
          {
            \"role\": \"user\",
            \"content\": \"Give me one surprising master's-level statistics fact in one line.\"
          }
        ],
        \"temperature\": 0.9,
        \"max_tokens\": 80
      }"
  )"

  node - "${RESPONSE_FILE}" "${HTTP_STATUS}" <<'EOF'
const fs = require("node:fs");

const [, , responsePath, httpStatus] = process.argv;
const body = fs.readFileSync(responsePath, "utf8");

let parsed;
try {
  parsed = JSON.parse(body);
} catch (error) {
  console.error(`HTTP ${httpStatus}`);
  console.error(body);
  process.exit(1);
}

if (httpStatus !== "200") {
  console.error(`HTTP ${httpStatus}`);
  console.error(parsed?.error?.message || body);
  process.exit(1);
}

const fact = parsed?.choices?.[0]?.message?.content?.trim();
if (!fact) {
  console.error("OpenAI returned a 200 response, but no assistant text was found.");
  process.exit(1);
}

console.log(fact);
EOF

  rm -f "${RESPONSE_FILE}"
}

main "$@"
