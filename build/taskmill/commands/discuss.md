---
description: "Discuss a backlog task"
argument-hint: "[task name]"
---

Discuss a backlog task. Does **not** write a plan.

- Finds task from `doc/backlog.md`: by name if provided, otherwise first `[>]`, then first `[ ]`. Skips `[N]` tasks (already claimed by another thread).
- **Claims the task** by changing its state to `[N]` where N is the lowest unused digit (1-9) among current `[N]` states in the backlog. A `[>]` task keeps its priority meaning — it just gets numbered like any other.
- Writes a `started: <ISO 8601 UTC timestamp>` sub-bullet to the task in `doc/backlog.md`, recording when discussion began.
- If the task has a `plan:` sub-bullet, reads and summarizes the existing plan, then continues discussion from there.
- Reads relevant codebase sections.
- Asks clarifying questions about approach, constraints, and design.
- Discussion continues until the user calls `finalize`.
- Do not enter plan mode or write plan files. This command is discussion only.
- Do not edit any files other than `doc/backlog.md` (for claiming the task). No code edits, no file creation.
