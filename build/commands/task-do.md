---
description: "Implement the next planned task (does not commit)"
model: sonnet
---

Read and follow ~/.claude/skills/workflow.md
Read and follow ~/.claude/skills/formats.md
Read and follow ~/.claude/skills/llm-context.md

## Behavior

Implement the next planned task. Does **not** commit.

1. Find next planned task: first `[>]` with `plan:`, then first `[p]` with `plan:`, then first `[ ]` with `plan:`.
   - Use `python ~/.claude/scripts/task_get.py --include-planned doc/backlog.md` to extract the task.
2. Read the plan file.
3. Read all files listed in `## Files` as initial context.
4. **Staleness check:** read the `started:` timestamp from the plan's YAML frontmatter and run `git log --since=<started-timestamp> -- <file1> <file2> ...` for the listed files. If changes are found, re-read affected files and revise plan steps before proceeding.
5. Implement each `- [ ]` step, marking as `- [x]` immediately after completion.
   - Use `python ~/.claude/scripts/task_complete.py <plan-file>` to mark steps.
6. If a step fails: mark `- [!]` and block the task.
   - Use `python ~/.claude/scripts/task_block.py <plan-file> "<reason>"`.
7. Run build + test after all steps (see `~/.claude/skills/csharp-build.md`).
8. If all steps complete:
   - Delete task from `doc/backlog.md` using `python ~/.claude/scripts/task_complete.py --delete doc/backlog.md`.
   - Update `doc/changelog.md` with a dated entry describing what was done.
9. Does **not** commit — user calls `mill-commit` when ready.
