#!/bin/bash
# PreToolUse hook: block or warn on dangerous git commands.
# Tool input JSON is passed via stdin.
set -euo pipefail

input=$(cat)
command=$(python -c "
import sys, json
try:
    data = json.loads('''$input''')
    print(data.get('tool_input', {}).get('command', ''))
except Exception:
    print('')
")

# Exit early if no command
if [[ -z "$command" ]]; then
  exit 0
fi

# DENY: git add -A / --all
if [[ "$command" =~ git[[:space:]]+add[[:space:]]+-A ]] ||
   [[ "$command" =~ git[[:space:]]+add[[:space:]]+--all ]]; then
  cat <<'EOF'
{
  "decision": "deny",
  "reason": "git add -A/--all is banned. It can stage unrelated changes. Use explicit file paths: git add <file1> <file2> ..."
}
EOF
  exit 0
fi

# DENY: git commit -a / -am
if [[ "$command" =~ git[[:space:]]+commit[[:space:]]+-a ]]; then
  cat <<'EOF'
{
  "decision": "deny",
  "reason": "git commit -a is banned. Stage files individually with git add, then commit."
}
EOF
  exit 0
fi

# DENY: git push --force / -f to main/master
if [[ "$command" =~ git[[:space:]]+push[[:space:]]+.*--force ]] ||
   [[ "$command" =~ git[[:space:]]+push[[:space:]]+-f ]]; then
  cat <<'EOF'
{
  "decision": "deny",
  "reason": "Force push is banned. It rewrites remote history and can cause data loss for collaborators."
}
EOF
  exit 0
fi

# ASK: git reset --hard
if [[ "$command" =~ git[[:space:]]+reset[[:space:]]+--hard ]]; then
  cat <<'EOF'
{
  "decision": "ask",
  "reason": "git reset --hard discards all uncommitted changes permanently. Consider git stash instead."
}
EOF
  exit 0
fi

# ASK: git clean -fd
if [[ "$command" =~ git[[:space:]]+clean[[:space:]]+-[a-z]*f[a-z]*d ]] ||
   [[ "$command" =~ git[[:space:]]+clean[[:space:]]+-[a-z]*d[a-z]*f ]]; then
  cat <<'EOF'
{
  "decision": "ask",
  "reason": "git clean -fd permanently deletes untracked files. Use git clean -nd first to preview."
}
EOF
  exit 0
fi

# Allow everything else
exit 0
