---
description: "Show task status and pick one to discuss"
---

Read and follow ~/.claude/skills/formats.md

## Behavior

Show task status and let the user pick one to discuss.

- Reads `doc/backlog.md`.
- Prints status summary: `Status: 1 prioritized | 1 in discussion | 2 planned | 3 unplanned | 1 blocked`.
- Groups open tasks by state: prioritized `[>]`, in discussion `[N]`, planned `[p]`, unplanned `[ ]`, blocked `[!]`.
- Shows plan file path and blocked reason if applicable.
- User picks a task number to start discussion (proceeds as `task-discuss`).
