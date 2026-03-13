#!/bin/bash
# PreToolUse hook: block direct edits to doc/backlog.md and .llm/plans/*.md.
# Tool input JSON is passed via stdin.
set -euo pipefail

input=$(cat)

file_path=$(echo "$input" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('tool_input', {}).get('file_path', ''))
")

tool_name=$(echo "$input" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('tool_name', ''))
")

if [[ "$file_path" == *"backlog.md" ]]; then
    echo "Direct edits to backlog.md are blocked. Use task_*.py scripts instead." >&2
    exit 2
fi

if [[ "$file_path" == *".llm/plans/"*".md" ]]; then
    if [[ "$tool_name" == "Write" && ! -f "$file_path" ]]; then
        exit 0
    fi
    echo "Direct edits to plan files are blocked. Use task_complete.py, task_block.py, or task_subbullet.py instead." >&2
    exit 2
fi

exit 0
