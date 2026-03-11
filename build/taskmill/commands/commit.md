---
description: "Commit and push"
argument-hint: "[--onmain] [message]"
---

Commit and push. No rebase.

- See `@taskmill:git` for full commit rules.
- **If on `main`/`master` and `--onmain` is not in the argument:** refuse to commit. Suggest a branch name based on the staged changes or recent context (e.g. `feature/revise-git-workflow`), prompt the user to confirm or provide an alternative name, then stop. Do not create the branch — `commit` only commits.
- **If on `main`/`master` and `--onmain` is in the argument:** proceed normally.
- Stages files individually, commits with title + bullet-point format, pushes.
- Sets upstream if needed: `git push --set-upstream origin <branch>`.
