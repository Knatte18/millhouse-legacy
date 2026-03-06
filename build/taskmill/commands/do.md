---
description: "Implement the next planned task (does not commit)"
model: sonnet
---

Implement the next planned task. Does **not** commit.

## Steps

1. Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_get.py --include-planned doc/backlog.md` to find the next planned task.
   - Priority: first `[>]` with `plan:`, then first `[p]` with `plan:`, then first `[ ]` with `plan:`.
2. Read the plan file.
3. Read all files listed in `## Files` as initial context.
4. **Staleness check:** read the `started:` timestamp from the plan's YAML frontmatter and run `git log --since=<started-timestamp> -- <file1> <file2> ...` for the listed files. If changes are found, re-read affected files and revise plan steps before proceeding.
5. Implement each `- [ ]` step, marking as `- [x]` immediately after completion.
6. If a step fails: mark `- [!]` and block the task via `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_block.py`.
7. Run build + test after all steps. Use @taskmill:csharp-build skill.
8. If all steps complete: run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_complete.py --delete doc/backlog.md`, then update `doc/changelog.md`.
9. Does **not** commit — user calls `commit` when ready.
