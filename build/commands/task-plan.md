---
description: "Write a plan from the current discussion"
argument-hint: "[task-name]"
---

Read and follow ~/.claude/skills/workflow.md
Read and follow ~/.claude/skills/formats.md
Read and follow ~/.claude/skills/llm-context.md

## Behavior

Write a plan from the current discussion.

- Takes task name from argument or infers from conversation.
- Creates `.llm/plans/YYYY-MM-DD-HHMMSS-<slug>.md` (using current UTC date and time) with:
  - **YAML frontmatter:** `started:` (copied from the task's `started:` sub-bullet in `doc/backlog.md`) and `finished:` (current UTC timestamp, matches filename timestamp)
  - **Context:** summary of discussion and key decisions
  - **Files:** flat list of file paths the plan expects to modify (used for staleness detection and fast implementation start)
  - **Steps:** concrete, actionable `- [ ]` items
- Adds `plan:` sub-bullet in `doc/backlog.md` linking to the plan file.
- Changes task state to `[p]` (planned) in `doc/backlog.md`.
- Steps must use concrete actions (e.g. `Regenerate build output following BUILD.md`), never `/task-*` commands or `~/.claude/skills/` references — the executor treats these as user-invocable, stalling execution.
