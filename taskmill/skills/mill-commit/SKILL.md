---
name: mill-commit
description: "Commit and push (no rebase)"
argument-hint: "[--onmain] [message]"
---

Commit and push. No rebase.

## Pre-commit steps

Run these before staging. Both are conditional — skip if the condition isn't met.

### 1. Ruff (Python files only)

If any changed files are `.py` files: run `ruff check --fix` on those files. If ruff reports unfixable errors, fix them manually before proceeding.

### 2. Codeguide sync (only if `_codeguide/` exists)

If `_codeguide/Overview.md` exists anywhere in the repo:

1. Run `git diff --name-only` to list changed source files.
2. Pipe the list to `python <codeguide-plugin-path>/codeguide_stale.py`. If it exits 0 (no stale docs), skip to staging.
3. For each stale doc path in the output, determine the codeguide-sync scope (project/module path relative to the `_codeguide/` root) and follow the `@codeguide:codeguide-sync <scope>` skill steps to update that doc.
4. Stage the updated doc files alongside source files.

The codeguide plugin path can be found at: `C:/Users/hanf/.claude/plugins/cache/codeguide/codeguide/1.0.0/codeguide/codeguide_stale.py` (or locate it via the installed plugin).

## Rules

- Use @taskmill:mill-git skill for full commit rules.
- **If on `main`/`master` and `--onmain` is not in the argument:** refuse to commit. Suggest a branch name based on staged changes or recent context (e.g. `feature/revise-git-workflow`), prompt the user to confirm or provide an alternative name, then stop. Do not create the branch.
- **If on `main`/`master` and `--onmain` is in the argument:** proceed normally.
- Stage files individually: `git add file1 file2` — never `git add .` or `git add -A`.
- Commit with title + bullet-point format (title summarizes the task, bullets explain key decisions).
- Push to remote. Set upstream if needed: `git push --set-upstream origin <branch>`.
- Never force-push. Never use `--no-verify`.
