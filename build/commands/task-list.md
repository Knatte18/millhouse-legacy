---
description: "Show task status and pick one to discuss"
---

Read and follow ~/.claude/skills/formats.md

## Behavior

Show task status and let the user pick one to discuss.

- Read `doc/backlog.md`.
- Print status summary: `Status: 1 prioritized | 1 in discussion | 2 planned | 3 unplanned | 1 blocked`.
- Group open tasks by state: prioritized `[>]`, in discussion `[N]`, planned `[p]`, unplanned `[ ]`, blocked `[!]`.
- Show plan file path and blocked reason if applicable.
- Ask user to pick a task number to start discussion. Once selected, proceed as `task-discuss`.
