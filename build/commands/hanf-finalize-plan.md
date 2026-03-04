---
description: "Write a plan from the current discussion"
argument-hint: "<task name>"
---

Read and follow ~/.claude/skills/workflow.md
Read and follow ~/.claude/skills/formats.md
Read and follow ~/.claude/skills/llm-context.md

## Behavior

Write a plan from the current discussion.

1. Take task name from argument or infer from conversation.
2. Create `.llm/plans/YYYY-MM-DD-HHMM-<slug>.md` (using current UTC date and time) with:
   - **Context:** summary of discussion and key decisions
   - **Steps:** concrete, actionable `- [ ]` items
3. Add `plan:` sub-bullet in `doc/backlog.md` linking to the plan file.
4. Change task state to `[p]` (planned) in `doc/backlog.md`.
