---
name: mill-retry
description: "Retry the first blocked task"
---

Retry the first blocked task.

## Steps

1. Find first `[!]` task with `plan:` sub-bullet in `doc/backlog.md`.
2. Read plan file, find first `- [!]` step (or first `- [ ]` if no `[!]`).
3. Implement remaining steps. After completing each step, run `python ${CLAUDE_SKILL_DIR}/../../scripts/task_complete.py <plan-file>` to mark it `[x]`.
4. If a step fails again: run `python ${CLAUDE_SKILL_DIR}/../../scripts/task_block.py <plan-file> "<reason>"` to mark it `[!]` and stay blocked.
5. If all steps complete: run `python ${CLAUDE_SKILL_DIR}/../../scripts/task_complete.py --delete doc/backlog.md`, update `doc/changelog.md`.
6. Does **not** commit.
