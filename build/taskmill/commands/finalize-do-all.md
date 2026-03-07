---
description: "Finalize the current discussion, then implement all planned tasks committing after each"
model: opus
---

Finalize the current discussion and implement all planned tasks, committing after each.

## Steps

1. **Branch check:** run `git branch --show-current`. If on `main`/`master` and `--onmain` is not in the argument: refuse. Suggest a branch name based on the task context (e.g. `feature/task-name`), prompt the user to create it and re-run. Do not create the branch. This branch is used for the entire batch.
2. Take task name from argument or infer from conversation.
3. Create `.llm/plans/YYYY-MM-DD-HHMMSS-<slug>.md` (using current UTC date and time) with YAML frontmatter, context, files, and steps.
4. Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_plan.py doc/backlog.md "<task-name>" <plan-path>` to change state to `[p]` and add/replace the `plan:` sub-bullet.
5. Loop: run `do-commit` (find next planned task, implement, commit) until `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_get.py --include-planned doc/backlog.md` exits with code 1 (no planned tasks remain).
