---
description: "Finalize, implement, and commit"
model: opus
---

Finalize the current discussion, implement the resulting task, and commit.

- **Branch check first:** run `git branch --show-current`. If on `main`/`master` and `--onmain` is not in the argument: refuse to proceed. Suggest a branch name based on the task context (e.g. `feature/task-name`), prompt the user to create it and re-run. Do not create the branch.
- Takes task name from argument or infers from conversation.
- Creates `.llm/plans/YYYY-MM-DD-HHMMSS-<slug>.md` with YAML frontmatter, context, files, and steps.
- Runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_plan.py doc/backlog.md "<task-name>" <plan-path>` to change state to `[p]` and add the `plan:` sub-bullet.
- Runs `do` on the resulting task: reads plan and listed files, staleness check, implements steps, runs build + test, updates backlog and changelog.
- Runs `commit`: stage individually, commit with title + bullet-point format, push. Set upstream if needed.
