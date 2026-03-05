---
description: "Discuss a backlog task without writing a plan"
argument-hint: "[task-name]"
---

Read and follow ~/.claude/skills/workflow.md
Read and follow ~/.claude/skills/formats.md
Read and follow ~/.claude/skills/llm-context.md

## Behavior

Discuss a backlog task. Does **not** write a plan.

- Finds task from `doc/backlog.md`: by name if provided, otherwise first `[>]`, then first `[ ]`. Skips `[N]` tasks (already claimed by another thread).
- **Claims the task** by running `python ~/.claude/scripts/task_claim.py doc/backlog.md [task-name]` to change its state to `[N]` and record `started:` timestamp.
- If the task has a `plan:` sub-bullet, reads and summarizes the existing plan, then continues discussion from there.
- Reads relevant codebase sections.
- Asks clarifying questions about approach, constraints, and design.
- Discussion continues until the user calls `task-plan`.
- Do not enter plan mode or write plan files. This command is discussion only.
