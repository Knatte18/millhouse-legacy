---
name: mill-do
description: "Implement the next planned task (does not commit)"
---

Implement the next planned task. Does **not** commit.

## Steps

1. Run `python ${CLAUDE_SKILL_DIR}/../../scripts/task_get.py --include-planned doc/backlog.md` to find the next planned task.
   - Priority: first `[>]` with `plan:`, then first `[p]` with `plan:`, then first `[ ]` with `plan:`.
2. Read the plan file.
3. Read all files listed in `## Files` as initial context.
4. **Staleness check:** read the `started:` timestamp from the plan's YAML frontmatter and run `git log --since=<started-timestamp> -- <file1> <file2> ...` for the listed files. If changes are found, re-read affected files and revise plan steps before proceeding.
5. Implement each `- [ ]` step. After completing each step, run `python ${CLAUDE_SKILL_DIR}/../../scripts/task_complete.py <plan-file>` to mark it `[x]`.
6. If a step fails: run `python ${CLAUDE_SKILL_DIR}/../../scripts/task_block.py <plan-file> "<reason>"` to mark it `[!]`, then block the backlog task via `python ${CLAUDE_SKILL_DIR}/../../scripts/task_block.py doc/backlog.md "<reason>" --name "<task-name>"`.
7. Run build + test after all steps (detect project language and use the matching `{lang}-build` skill — see `@taskmill:mill-workflow` Language Detection).
8. If all steps complete: run `python ${CLAUDE_SKILL_DIR}/../../scripts/task_complete.py --delete doc/backlog.md "<task-name>"`, then update `doc/changelog.md`.
9. Does **not** commit — user calls `commit` when ready.
