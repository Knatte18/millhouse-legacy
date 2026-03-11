---
description: "Finalize the current discussion and implement the task"
model: opus
---

Finalize the current discussion and immediately implement the resulting task. Does **not** commit.

- Takes task name from argument or infers from conversation.
- Creates `.llm/plans/YYYY-MM-DD-HHMMSS-<slug>.md` (using current UTC date and time) with YAML frontmatter, context, files, and steps. (Same as `finalize`.)
- Runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_plan.py doc/backlog.md "<task-name>" <plan-path>` to change state to `[p]` and add the `plan:` sub-bullet.
- Runs `do` on the resulting task: reads plan and listed files, staleness check, implements steps, runs build + test, updates backlog and changelog.
- Does **not** commit — user calls `commit` when ready.
