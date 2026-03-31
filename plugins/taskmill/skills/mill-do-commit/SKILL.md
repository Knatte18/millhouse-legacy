---
name: mill-do-commit
description: "Implement the next planned task and commit"
---

Implement the next planned task and commit.

## Steps

1. **Branch check:** run `git branch --show-current`. If on `main`/`master`:
   1. Derive a branch name from the task title slug (e.g. `feature/revise-git-workflow`).
   2. Prompt: *"You're on **main**. Create branch **`<name>`** and continue there? You can also provide a different name."*
   3. Wait for user confirmation or an alternative name.
   4. Run `git checkout -b <name>` to create and switch to the branch.
2. Follow the @taskmill:mill-do skill steps to implement the next planned task.
3. Follow the @taskmill:mill-commit skill rules to commit and push.
