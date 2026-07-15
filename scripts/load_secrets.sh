# Export Converse secrets from the macOS login Keychain into the current shell.
# MUST be sourced, not executed (a subprocess can't export into your shell):
#     source scripts/load_secrets.sh
# Populated earlier by scripts/store_secrets.sh.

# Guard: refuse to run if executed instead of sourced.
_converse_sourced=0
if [ -n "${ZSH_VERSION:-}" ]; then
  case "${ZSH_EVAL_CONTEXT:-}" in *:file) _converse_sourced=1 ;; esac
elif [ -n "${BASH_VERSION:-}" ]; then
  [ "${BASH_SOURCE[0]}" != "${0}" ] && _converse_sourced=1
fi
if [ "$_converse_sourced" -eq 0 ]; then
  echo "load_secrets.sh must be SOURCED, not executed:  source scripts/load_secrets.sh" >&2
  exit 1
fi
unset _converse_sourced

# service-name -> env var name
export NEON_DIRECT_URL="$(security find-generic-password -s converse-neon-direct-url    -w 2>/dev/null || true)"
export NEON_POOLED_URL="$(security find-generic-password -s converse-neon-pooled-url    -w 2>/dev/null || true)"
export OPENAI_API_KEY="$(security find-generic-password  -s converse-openai-api-key     -w 2>/dev/null || true)"
export ANTHROPIC_API_KEY="$(security find-generic-password -s converse-anthropic-api-key -w 2>/dev/null || true)"

# Report anything missing so a silent typo in a service name is visible.
_converse_missing=""
for _pair in \
  "NEON_DIRECT_URL:converse-neon-direct-url" \
  "NEON_POOLED_URL:converse-neon-pooled-url" \
  "OPENAI_API_KEY:converse-openai-api-key" \
  "ANTHROPIC_API_KEY:converse-anthropic-api-key"; do
  _var="${_pair%%:*}"
  eval "_val=\${$_var}"
  [ -z "$_val" ] && _converse_missing="${_converse_missing} ${_pair#*:}"
done

if [ -n "$_converse_missing" ]; then
  echo "Converse: loaded, but missing from Keychain ->${_converse_missing}" >&2
  echo "  add them with: ./scripts/store_secrets.sh" >&2
else
  echo "Converse: all 4 secrets loaded into this shell."
fi
unset _converse_missing _pair _var _val
