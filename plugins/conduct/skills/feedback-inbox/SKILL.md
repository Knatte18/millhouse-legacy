---
name: feedback-inbox
description: Import open GitHub feedback issues into the local kanban board and close them.
---

# feedback-inbox

One-shot. Fetch open GitHub issues labeled `feedback` from Knatte18/millhouse, add each as a Backlog task in `.kanban.md`, and close the issues.

---

## Steps

### Step 1: Fetch open feedback issues

```bash
gh issue list --repo Knatte18/millhouse --label feedback --state open --json number,title,body
```

If the result is empty, report `No open feedback issues` and stop.

### Step 2: Check board exists

If `.kanban.md` does not exist, stop and tell the user to run `helm-setup` first.

### Step 3: Add tasks to board

For each issue returned in step 1:

1. Read `.kanban.md`. Append a new task block under the `## Backlog` heading (before the next `##` heading or end of file):

If no body:

```markdown
### <issue title> [backlog]
```

If the issue has a body, use an indented ` ```md ` code block (plain text descriptions are not parsed by the kanban.md extension and are destroyed on drag-and-drop):

```markdown
### <issue title> [backlog]

    ```md
    <issue body>
    ```
```

### Step 4: Validate

Validate `.kanban.md` per `plugins/helm/doc/modules/validation.md`:

1. Exactly one `#` heading at line 1.
2. Every `##` heading is one of: Backlog, In Progress, Done, Blocked.
3. No `##` headings outside that set.
4. Every `###` heading appears after a `##` heading.
5. No non-blank lines between the `#` heading and the first `##`.

If validation fails, report the violation and stop.

### Step 5: Close issues on GitHub

For each issue processed:

```bash
gh issue close <number> --repo Knatte18/millhouse
```

### Step 6: Commit and push

Commit `.kanban.md` with message: `kanban: import <N> feedback issues from GitHub`

Push immediately.

### Step 7: Report

```
<N> issues processed and added to Backlog
```
