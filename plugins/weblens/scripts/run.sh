#!/bin/bash
# Wrapper to ensure node is on PATH in sandboxed environments.
# The Bash tool sandbox may strip PATH, causing "node: command not found" (exit 127).
for d in "/c/Program Files/nodejs" "/usr/local/bin" "/usr/bin"; do
  [ -d "$d" ] && PATH="$d:$PATH"
done
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec node "$SCRIPT_DIR/fetch.mjs" "$@"
