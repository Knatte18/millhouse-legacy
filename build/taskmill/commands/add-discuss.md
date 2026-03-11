---
description: "Add a task and start discussing it"
argument-hint: "Title: description"
---

Add a new task to the backlog and immediately start discussing it.

- Takes `Title: description` as argument. Colon splitting follows the same rules as `add`: part before colon becomes the bold title, part after becomes the description.
- Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_add.py doc/backlog.md "<full argument>"` to append the task to the backlog.
- Extract the title: part before the first colon, or the full argument if no colon is present.
- Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_claim.py doc/backlog.md "<title>"` to claim the newly added task (assigns thread number, records started timestamp).
- Continue as `discuss`: read relevant codebase sections, ask clarifying questions about approach, constraints, and design. Do not write a plan file — discussion continues until the user calls `finalize`.
