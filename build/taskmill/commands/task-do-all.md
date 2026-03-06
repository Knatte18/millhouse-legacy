---
description: "Implement all planned tasks, committing after each"
model: sonnet
---

Implement all planned tasks. Commits after **each** completed task.

## Steps

Loop through planned tasks using `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_get.py --include-planned doc/backlog.md` (priority: `[>]` → `[p]` → `[ ]`, all with `plan:` sub-bullet).

For each task:

1. Read the plan file and all files listed in `## Files`.
2. **Staleness check:** read the `started:` timestamp from the plan's YAML frontmatter and run `git log --since=<started-timestamp> -- <file1> <file2> ...` for the listed files. If changes are found, re-read affected files and revise plan steps.
3. Implement each `- [ ]` step, marking as `- [x]`.
4. If a step fails: mark `- [!]`, block the task via `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_block.py`, move to the next task.
5. Run build + test. Use @taskmill:csharp-build skill.
6. Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_complete.py --delete doc/backlog.md`, update `doc/changelog.md`.
7. Commit and push using @taskmill:git skill rules (stage files individually, title + bullet-point format, set upstream if needed).

Stop when no planned tasks remain.
