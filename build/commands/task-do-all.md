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

- Loops through planned tasks using `python ~/.claude/scripts/task_get.py --include-planned doc/backlog.md` (priority: `[>]` → `[p]` → `[ ]`).
- For each task:
  1. Read the plan file and all files listed in `## Files`. Run the same staleness check as `task-do` (using `started:` from plan frontmatter); if changes found, re-read affected files and revise plan steps.
  2. Implement each `- [ ]` step, marking as `- [x]` using `python ~/.claude/scripts/task_complete.py <plan-file>`.
  3. If a step fails: mark `- [!]` using `python ~/.claude/scripts/task_block.py <plan-file> "<reason>"`, move to the next task.
  4. Run build + test.
  5. Delete task from `doc/backlog.md` using `python ~/.claude/scripts/task_complete.py --delete doc/backlog.md`. Update `doc/changelog.md`.
  6. Commit and push (stage files individually, commit with title + bullet-point format, push with upstream if needed).
- Stops when no planned tasks remain.
