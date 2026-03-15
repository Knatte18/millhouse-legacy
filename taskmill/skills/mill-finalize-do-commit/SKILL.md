---
name: mill-finalize-do-commit
description: "Finalize, implement, and commit"
argument-hint: "[--onmain]"
---

Finalize the current discussion, implement the resulting task, and commit.

## Steps

1. **Branch check:** run `git branch --show-current`. If on `main`/`master` and `--onmain` is not in the argument: refuse. Suggest a branch name based on the task context (e.g. `feature/task-name`), prompt the user to create it and re-run. Do not create the branch.
2. Follow the @taskmill:mill-finalize skill steps to write a plan from the current discussion.
3. Follow the @taskmill:mill-do skill steps to implement the resulting task.
4. Follow the @taskmill:mill-commit skill rules to commit and push.
