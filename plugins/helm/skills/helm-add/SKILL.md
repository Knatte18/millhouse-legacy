---
name: helm-add
description: Create a new task on the local kanbn board.
---

# helm-add

One-shot. Add a task to the kanbn board under Backlog.

For kanbn file format details, see `plugins/helm/doc/modules/kanbn-format.md`.

---

## Usage

```
helm-add <title>: <body>
helm-add <title>
```

Text before the first colon is the title. Text after is the body. No colon means title only.

## Steps

### Step 1: Check board exists

If `.kanbn/index.md` does not exist, stop and tell the user to run `helm-setup` first.

### Step 2: Parse input

Split the argument on the first `:` character.

- Left side (trimmed) → task title
- Right side (trimmed) → task description (may be empty)

### Step 3: Generate task ID

Slugify the title: lowercase, replace spaces with hyphens, remove special characters. Example: "Add OAuth Support" → `add-oauth-support`.

### Step 4: Create task file

Write `.kanbn/tasks/<task-id>.md`:

```markdown
---
created: <ISO timestamp>
updated: <ISO timestamp>
assigned: ""
tags: []
---

# <Title>

<Description, if provided>
```

### Step 5: Add to board

Read `.kanbn/index.md`. Add `- [<task-id>](tasks/<task-id>.md)` as a new list item under the `## Backlog` heading (before the next `##` heading or end of file).

### Step 6: Report

```
Added: <title> (<task-id>)
```
