---
description: "Retry the first blocked task"
---

Read and follow ~/.claude/skills/workflow.md
Read and follow ~/.claude/skills/formats.md
Read and follow ~/.claude/skills/llm-context.md

## Behavior

Retry the first blocked task.

- Finds first `[!]` task with `plan:` sub-bullet in `doc/backlog.md`.
- Reads plan file, finds first `- [!]` step (or first `- [ ]` if no `[!]`).
- Implements remaining steps, marking as `- [x]` using `python ~/.claude/scripts/task_complete.py <plan-file>`.
- If a step fails again: marks `- [!]` using `python ~/.claude/scripts/task_block.py <plan-file> "<reason>"` and stays blocked.
- If all steps complete: deletes task from `doc/backlog.md` using `python ~/.claude/scripts/task_complete.py --delete doc/backlog.md`, updates `doc/changelog.md`.
- Does **not** commit.
