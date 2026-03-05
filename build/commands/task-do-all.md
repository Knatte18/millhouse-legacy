---
description: "Implement all planned tasks, committing after each"
model: sonnet
---

Read and follow ~/.claude/skills/workflow.md
Read and follow ~/.claude/skills/formats.md
Read and follow ~/.claude/skills/llm-context.md
Read and follow ~/.claude/skills/git.md

## Behavior

Implement all planned tasks. Commits after **each** completed task.

Loop through planned tasks using `python ~/.claude/scripts/task_get.py --include-planned doc/backlog.md` (priority: `[>]` → `[p]` → `[ ]` with `plan:` sub-bullet).

For each task:
1. Read the plan file and all files listed in `## Files`. Run staleness check (using `started:` from plan frontmatter): `git log --since=<started-timestamp> -- <file1> <file2> ...`. If changes found, re-read affected files and revise plan steps.
2. Implement each `- [ ]` step, marking as `- [x]` with `python ~/.claude/scripts/task_complete.py <plan-file>`.
3. If a step fails: mark `- [!]` with `python ~/.claude/scripts/task_block.py <plan-file> "<reason>"`, move to the next task.
4. Run build + test (see `~/.claude/skills/csharp-build.md`).
5. Delete task from `doc/backlog.md` with `python ~/.claude/scripts/task_complete.py --delete doc/backlog.md`. Update `doc/changelog.md`.
6. Commit and push following `~/.claude/skills/git.md` rules.

Stop when `python ~/.claude/scripts/task_get.py --include-planned doc/backlog.md` returns exit code 1 (no planned tasks remain).
