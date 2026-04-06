---
name: legacy-mill-retry
description: "Retry the first blocked task"
---

Retry the first blocked task.

## Steps

1. Find first `[!]` task with `plan:` sub-bullet in `_millhouse/taskmill/backlog.md`.
2. Read plan file, find first `- [!]` step (or first `- [ ]` if no `[!]`).
3. Implement remaining steps. After completing each step, run `python ${CLAUDE_SKILL_DIR}/../../scripts/task_complete.py <plan-file>` to mark it `[x]`.
4. If a step fails again: run `python ${CLAUDE_SKILL_DIR}/../../scripts/task_block.py <plan-file> "<reason>"` to mark it `[!]` and stay blocked.
5. Run build + test after all steps (detect project language and use the matching `{lang}-build` skill — see `@mill:workflow` Language Detection).
6. **Codeguide update (only if `_codeguide/` exists):** If `_codeguide/Overview.md` exists, run `@mill:codeguide-update` (no arguments — defaults to git diff).
7. If all steps complete: run `python ${CLAUDE_SKILL_DIR}/../../scripts/task_complete.py --delete _millhouse/taskmill/backlog.md "<task-name>"`, update `_millhouse/taskmill/changelog.md`.
8. Does **not** commit.
