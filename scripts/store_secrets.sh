#!/usr/bin/env bash
# Prompt for each Converse secret and store it in the macOS login Keychain.
# Run directly:  ./scripts/store_secrets.sh
# Re-run any time to update a value (-U overwrites). Blank input skips an item.

set -euo pipefail

account="${USER}"

# service-name : human label
items=(
  "converse-neon-direct-url:Neon DIRECT connection string (schema/DDL)"
  "converse-neon-pooled-url:Neon POOLED connection string (-pooler, app runtime)"
  "converse-openai-api-key:OpenAI API key"
  "converse-anthropic-api-key:Anthropic API key"
)

for entry in "${items[@]}"; do
  service="${entry%%:*}"
  label="${entry#*:}"

  printf 'Enter %s\n  [%s] (blank to skip): ' "$label" "$service"
  read -rs value
  echo

  if [[ -z "$value" ]]; then
    echo "  · skipped $service"
    continue
  fi

  # Confirm what was captured before storing (masked: length + first/last few chars).
  n=${#value}
  if (( n > 8 )); then
    preview="${value:0:3}…${value: -3}"
  else
    preview="(too short to preview safely)"
  fi
  echo "  captured ${n} chars: ${preview}"

  # -U overwrites an existing item; -T pre-authorizes `security` so reads don't prompt.
  security add-generic-password -U -a "$account" -s "$service" -T /usr/bin/security -w "$value"

  # Round-trip: read it back and confirm the stored value is non-empty and same length.
  stored="$(security find-generic-password -s "$service" -w 2>/dev/null || true)"
  if [[ -z "$stored" ]]; then
    echo "  ✗ FAILED — nothing stored for $service" >&2
  elif [[ "${#stored}" -ne "$n" ]]; then
    echo "  ✗ MISMATCH — stored ${#stored} chars, expected ${n}" >&2
  else
    echo "  ✓ verified ${#stored} chars in Keychain"
  fi
done

unset value stored preview n

echo
echo "Done. Load into a shell with:  source scripts/load_secrets.sh"
