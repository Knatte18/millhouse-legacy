---
description: "Retry the first blocked task"
---

Retry the first blocked task.

- Finds first `[!]` task with `plan:` sub-bullet in `doc/backlog.md`.
- Reads plan file, finds first `- [!]` step (or first `- [ ]` if no `[!]`).
- Implements remaining steps. After completing each step, runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_complete.py <plan-file>` to mark it `[x]`.
- If a step fails again: runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_block.py <plan-file> "<reason>"` to mark it `[!]` and stays blocked.
- If all steps complete: deletes task from `doc/backlog.md` (via `--delete`), updates changelog.
- Does **not** commit.
