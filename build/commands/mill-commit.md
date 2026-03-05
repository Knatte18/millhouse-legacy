---
description: "Commit and push (no rebase)"
---

Read and follow ~/.claude/skills/git.md

## Behavior

Commit and push. No rebase.

- Stage files individually by name (never `git add .` or `git add -A`).
- Commit with title + bullet-point format (see `~/.claude/skills/git.md` for message format).
- Push to remote. Set upstream if needed: `git push --set-upstream origin <branch>`.
- Never rebase. Never force-push.
