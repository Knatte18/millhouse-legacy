---
name: helm-status
description: Dashboard showing all active worktrees and their state.
---

# helm-status

Dashboard. Read-only.

Shows all active worktrees and their state by reading `git worktree list`, each worktree's `_helm/scratch/status.md`, and `.kanban.md`.

```
Board (.kanban.md):
  Backlog:       2 tasks
  In Progress:   2 tasks (1 implementing, 1 reviewing)
  Done:          4 tasks
  Blocked:       0 tasks

Worktrees:
  feature/auth        [implementing]  3/5 steps    parent: main
  feature/csv-export  [planned]       0/3 steps    parent: main
```

<!-- TODO: Full implementation in Phase 4.1 -->
