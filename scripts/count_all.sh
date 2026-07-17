#!/usr/bin/env bash
# Exact row count of every public table.
#     ./scripts/count_all.sh neon | neon-direct | local | <postgres url>
# Default target: neon (the pooled Neon url from the Keychain).
set -euo pipefail

target="${1:-neon}"
case "$target" in
  neon)        url="$(security find-generic-password -s converse-neon-pooled-url -w 2>/dev/null || true)" ;;
  neon-direct) url="$(security find-generic-password -s converse-neon-direct-url -w 2>/dev/null || true)" ;;
  local)       url="postgresql://postgres:postgres@localhost:5432/convo_maker" ;;
  *)           url="$target" ;;  # treat anything else as a literal connection string
esac

[ -n "$url" ] || { echo "no connection url for '$target' (Keychain miss?)" >&2; exit 1; }

exec psql "$url" -f "$(dirname "$0")/count_all.sql"
