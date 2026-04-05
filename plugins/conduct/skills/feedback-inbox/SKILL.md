---
name: feedback-inbox
description: Import open GitHub feedback issues into the local kanban board and close them.
---

# feedback-inbox

One-shot. Fetch open GitHub issues labeled `feedback` from Knatte18/millhouse, add each as a Backlog task in `kanbans/backlog.kanban.md`, and close the issues.

---

## Steps

### Step 1: Fetch open feedback issues

```bash
gh issue list --repo Knatte18/millhouse --label feedback --state open --json number,title,body
```

If the result is empty, report `No open feedback issues` and stop.

### Step 2: Check backlog exists

If `kanbans/backlog.kanban.md` does not exist, stop and tell the user to run `helm-setup` first.

### Step 3: Add tasks to backlog

For each issue returned in step 1:

1. Read `kanbans/backlog.kanban.md`. Append a new task block under the `## Backlog` heading (before the next `##` heading or end of file):

If no body:

```markdown
### <issue title>
```

If the issue has a body, use an indented ` ```md ` code block (plain text descriptions are not parsed by the kanban.md extension and are destroyed on drag-and-drop):

```markdown
### <issue title>

    ```md
    <issue body>
    ```
```

### Step 4: Validate

Validate `kanbans/backlog.kanban.md` per `plugins/helm/doc/modules/validation.md` (3-column rules: Backlog, Spawn, Delete). If validation fails, report the violation and stop.

### Step 5: Close issues on GitHub

For each issue processed:

```bash
gh issue close <number> --repo Knatte18/millhouse
```

### Step 6: Commit and push

Since backlog is git-tracked:

```bash
git add kanbans/backlog.kanban.md
git commit -m "sync: import <N> feedback issues"
git push
```

### Step 7: Report

```
<N> issues processed and added to Backlog
```
