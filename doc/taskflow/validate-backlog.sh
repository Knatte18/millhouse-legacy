#!/bin/bash
# PreToolUse hook: block direct edits to doc/backlog.md.
# Tool input JSON is passed via stdin.

file_path=$(python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('file_path', ''))
except Exception:
    print('')
")

if [[ "$file_path" == *"backlog.md" ]]; then
    echo "Direct edits to backlog.md are blocked. Use task_*.py scripts instead." >&2
    exit 2
fi

exit 0
