#!/usr/bin/env bash
# Run the p3-9 key-alignment check against the live DB.
#
#   ./run.sh                 # uses $DATABASE_URL or the local default
#   DATABASE_URL=... ./run.sh
#
# Mirrors app/config.py's default DSN so it hits the same DB the backend uses.
set -euo pipefail

DSN="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/convo_maker}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "DB: ${DSN%%\?*}"
psql "$DSN" -f "$HERE/check_p3-9.sql"
