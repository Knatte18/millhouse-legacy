---
name: mill-finalize-do-all
description: "Finalize, then implement all planned tasks"
argument-hint: "[--onmain]"
---

Finalize the current discussion and implement all planned tasks, committing after each.

## Steps

1. **Branch check:** run `git branch --show-current`. If on `main`/`master` and `--onmain` is not in the argument: refuse. Suggest a branch name based on the task context (e.g. `feature/task-name`), prompt the user to create it and re-run. Do not create the branch. This branch is used for the entire batch.
2. Follow the @taskmill:mill-finalize skill steps to write a plan from the current discussion.
3. Loop until no planned tasks remain (`python ${CLAUDE_SKILL_DIR}/../../scripts/task_get.py --include-planned doc/backlog.md` exits with code 1):
   1. Follow the @taskmill:mill-do skill steps to implement the next planned task.
   2. Follow the @taskmill:mill-commit skill rules to commit and push.
