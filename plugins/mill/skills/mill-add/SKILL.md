---
name: mill-add
description: Create a new task in tasks.md.
---

# mill-add

One-shot. Add a task to `tasks.md` in the project root.

For tasks.md file format details, see `plugins/mill/doc/formats/tasksmd.md`.

---

## Usage

```
mill-add <title>: <body>
mill-add <title>
```

Text before the first colon is the title. Text after is the body. No colon means title only.

## Steps

### Step 1: Check tasks.md exists

If `tasks.md` does not exist in the project root (the working directory where `_millhouse/` lives), stop and tell the user to run `mill-setup` first.

### Step 2: Parse input

Split the argument on the first `:` character.

- Left side (trimmed) -> task title
- Right side (trimmed) -> task description (may be empty)

### Step 3: Add task to tasks.md

Read `tasks.md`. Append a new task block at the end of the file:

If no description:

```markdown
## <Title>
```

If description provided:

```markdown
## <Title>
- <Description>
```

### Step 4: Validate

Validate `tasks.md` per `doc/modules/validation.md` (tasks.md structural rules). If validation fails, report the issue to the user and stop.

### Step 5: Commit and push

```bash
git add tasks.md
git commit -m "task: add <title>"
git push
```

### Step 6: Report

```
Added: <title>
```
