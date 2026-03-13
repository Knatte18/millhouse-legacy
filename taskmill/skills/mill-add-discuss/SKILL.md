---
name: mill-add-discuss
description: "Add a task and start discussing it"
argument-hint: "<Title: description>"
---

Add a new task to the backlog and immediately start discussing it.

## Steps

1. Run `python ${CLAUDE_SKILL_DIR}/../../scripts/task_add.py doc/backlog.md "<full argument>"` to append the task to the backlog.
2. Extract the title: part before the first colon, or the full argument if no colon is present.
3. Run `python ${CLAUDE_SKILL_DIR}/../../scripts/task_claim.py doc/backlog.md "<title>"` to claim the newly added task (assigns thread number, records started timestamp).
4. Continue as `discuss`: read relevant codebase sections, ask clarifying questions about approach, constraints, and design.
5. Discussion continues until the user calls `finalize`. Do not write a plan file here.
