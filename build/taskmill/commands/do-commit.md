---
description: "Implement the next planned task and commit"
model: opus
---

Implement the next planned task and commit. Combines `do` then `commit`.

- **Branch check first:** run `git branch --show-current`. If on `main`/`master`:
  1. Derive a branch name from the task title slug (e.g. `feature/revise-git-workflow`).
  2. Prompt: *"You're on **main**. Create branch **`<name>`** and continue there? You can also provide a different name."*
  3. Wait for user confirmation or an alternative name.
  4. Create the branch (`git checkout -b <name>`) and switch to it.
- Run `do` (implement the next planned task, mark steps, run build + test, update backlog and changelog).
- Run `commit` (stage individually, commit with title + bullet-point format, push).
