---
name: helm-add
description: Create a new task on the local kanban board.
---

# helm-add

One-shot. Add a task to the `.kanban.md` board under Backlog.

For kanban.md file format details, see `plugins/helm/doc/modules/kanban-format.md`.

---

## Usage

```
helm-add <title>: <body>
helm-add <title>
```

Text before the first colon is the title. Text after is the body. No colon means title only.

## Steps

### Step 1: Check board exists

If `.kanban.md` does not exist, stop and tell the user to run `helm-setup` first.

### Step 2: Parse input

Split the argument on the first `:` character.

- Left side (trimmed) → task title
- Right side (trimmed) → task description (may be empty)

### Step 3: Add task to board

Run `date -u +%Y-%m-%d` to get the current UTC date. **Do not guess or fabricate a date.**

Read `.kanban.md`. Add a new task block under the `## Backlog` heading (before the next `##` heading or end of file):

```markdown
### <Title>
- created: <current UTC date>

<Description, if provided>
```

### Step 4: Validate

Validate `.kanban.md` per `doc/modules/validation.md`. If validation fails, report the issue to the user and stop.

### Step 5: Report

```
Added: <title>
```
