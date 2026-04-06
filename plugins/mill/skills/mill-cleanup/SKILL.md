---
name: mill-cleanup
description: Remove tasks from the Delete column in the backlog.
---

# mill-cleanup

One-shot. Remove all tasks from the `## Delete` column in `_millhouse/backlog.kanban.md`.

---

## Steps

### Step 1: Check backlog exists

If `_millhouse/backlog.kanban.md` does not exist: report "No backlog found. Run mill-setup first." Stop.

### Step 2: Find tasks to delete

Read `_millhouse/backlog.kanban.md`. Find all `###` headings under the `## Delete` column.

If Delete column is empty: report "Delete column is empty. Nothing to clean up." Stop.

### Step 3: Remove tasks

Remove all task blocks from the `## Delete` column (from `### Title` to just before the next `###` or `##`).

### Step 4: Validate

Validate `_millhouse/backlog.kanban.md` per `doc/modules/validation.md` (3-column rules: Backlog, Spawn, Delete). If validation fails, report the issue to the user and stop.

### Step 5: Commit and push

Since backlog is git-tracked:

```bash
git add _millhouse/backlog.kanban.md
git commit -m "chore: clean up <N> discarded tasks"
git push
```

### Step 6: Report

```
Cleaned up: <N> task(s) removed from Delete column.
```
