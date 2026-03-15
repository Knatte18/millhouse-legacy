---
name: mill-do-all
description: "Implement all planned tasks, committing after each"
---

Implement all planned tasks, committing after each.

## Steps

1. **Branch check:** run `git branch --show-current`. If on `main`/`master`:
   1. Derive a branch name from the first planned task's title slug.
   2. Prompt: *"You're on **main**. Create branch **`<name>`** and continue there? You can also provide a different name."*
   3. Wait for user confirmation or an alternative name.
   4. Run `git checkout -b <name>` to create and switch to the branch. This branch is used for the entire batch.
2. Loop until no planned tasks remain (`python ${CLAUDE_SKILL_DIR}/../../scripts/task_get.py --include-planned doc/backlog.md` exits with code 1):
   1. Follow the @taskmill:mill-do skill steps to implement the next planned task.
   2. Follow the @taskmill:mill-commit skill rules to commit and push.
