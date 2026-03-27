---
name: mill-list
description: "Show task status and pick one to discuss"
---

Show task status and let the user pick one to discuss.

## Steps

1. Read `_taskmill/backlog.md`.
2. Print status summary: `Status: N prioritized | N in discussion | N planned | N unplanned | N blocked`.
3. Group open tasks by state: prioritized `[>]`, in discussion `[N]`, planned `[p]`, unplanned `[ ]`, blocked `[!]`.
4. Show plan file path and blocked reason if applicable.
5. User picks a task number to start discussion (proceeds as `discuss`).

Use @taskmill:mill-formats skill for backlog format rules.
