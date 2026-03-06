---
description: "Commit and push (no rebase)"
---

Commit and push. No rebase.

## Rules

- Use @taskmill:git skill for full commit rules.
- Stage files individually: `git add file1 file2` — never `git add .` or `git add -A`.
- Commit with title + bullet-point format (title summarizes the task, bullets explain key decisions).
- Push to remote. Set upstream if needed: `git push --set-upstream origin <branch>`.
- Never force-push. Never use `--no-verify`.
