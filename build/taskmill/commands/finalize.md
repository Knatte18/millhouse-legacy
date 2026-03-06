---
description: "Write a plan from the current discussion"
argument-hint: "<task name>"
---

Write an implementation plan from the current discussion.

## Steps

1. Take task name from argument or infer from conversation.
2. Create `.llm/plans/YYYY-MM-DD-HHMMSS-<slug>.md` (using current UTC date and time) with:
   - **YAML frontmatter:** `started:` (copied from the task's `started:` sub-bullet in `doc/backlog.md`) and `finished:` (current UTC timestamp, matches filename timestamp)
   - **Context:** summary of discussion and key decisions
   - **Files:** flat list of file paths the plan expects to modify (used for staleness detection and fast implementation start)
   - **Steps:** concrete, actionable `- [ ]` items
3. Add `plan:` sub-bullet in `doc/backlog.md` linking to the plan file.
4. Change task state to `[p]` (planned) in `doc/backlog.md`.

## Rules

- Steps must use concrete actions (e.g. `Regenerate build output following BUILD.md`), never `/taskmill.*` commands or `@taskmill:` skill references — the executor treats these as requiring user invocation or skill loading, stalling execution.
- Do not edit any files other than `doc/backlog.md` and `.llm/plans/`. No code edits, no build changes.
- Use @taskmill:formats skill for plan and backlog format rules.
