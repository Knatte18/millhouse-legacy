---
name: mill-add
description: Create a new task on the local kanban board.
---

# mill-add

One-shot. Add a task to the `## Backlog` column in `_millhouse/backlog.kanban.md`.

For kanban.md file format details, see `plugins/mill/doc/modules/kanban-format.md`.

---

## Usage

```
mill-add <title>: <body>
mill-add <title>
```

Text before the first colon is the title. Text after is the body. No colon means title only.

## Steps

### Step 1: Check backlog exists

If `_millhouse/backlog.kanban.md` does not exist, stop and tell the user to run `mill-setup` first.

### Step 2: Parse input

Split the argument on the first `:` character.

- Left side (trimmed) → task title
- Right side (trimmed) → task description (may be empty)

### Step 3: Add task to backlog

Read `_millhouse/backlog.kanban.md`. Add a new task block under the `## Backlog` column (before the next `##` heading or end of file):

If no description:

```markdown
### <Title>
```

If description provided, use an indented ` ```md ` code block (plain text descriptions are not parsed by the kanban.md extension and are destroyed on drag-and-drop):

```markdown
### <Title>

    ```md
    <Description>
    ```
```

### Step 4: Validate

Validate `_millhouse/backlog.kanban.md` per `doc/modules/validation.md` (3-column rules: Backlog, Spawn, Delete). If validation fails, report the issue to the user and stop.

### Step 5: Commit and push

Since backlog is git-tracked, commit and push:

```bash
git add _millhouse/backlog.kanban.md
git commit -m "add: <title>"
git push
```

### Step 6: Report

```
Added: <title>
```
