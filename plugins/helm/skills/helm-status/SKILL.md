---
name: helm-status
description: Dashboard showing all active worktrees and their state.
---

# helm-status

Dashboard. Read-only.

Shows all active worktrees and their state by reading `git worktree list`, each worktree's `_helm/scratch/status.md`, and `.kanbn/index.md`.

```
Board (.kanbn/index.md):
  Backlog:       2 tasks
  Discussing:    1 task
  Planned:       0 tasks
  Implementing:  1 task (Step 3/5)
  Reviewing:     0 tasks
  Blocked:       0 tasks
  Done:          4 tasks

Worktrees:
  feature/auth        [implementing]  3/5 steps    parent: main
  feature/csv-export  [planned]       0/3 steps    parent: main
```

<!-- TODO: Full implementation in Phase 4.1 -->
