---
description: "Retry the first blocked task"
---

Read and follow ~/.claude/skills/workflow.md
Read and follow ~/.claude/skills/formats.md

## Behavior

Retry the first blocked task.

- Find first `[!]` task with `plan:` sub-bullet in `doc/backlog.md`.
- Read plan file, find first `- [!]` step (or first `- [ ]` if no `[!]`).
- Implement remaining steps, marking as `- [x]` with `python ~/.claude/scripts/task_complete.py <plan-file>`.
- If a step fails again: mark `- [!]` with `python ~/.claude/scripts/task_block.py <plan-file> "<reason>"` and stay blocked.
- If all steps complete: delete task from `doc/backlog.md` with `python ~/.claude/scripts/task_complete.py --delete doc/backlog.md`. Update `doc/changelog.md`.
- Does **not** commit.
