---
name: helm-add
description: Create a new task on the local kanbn board.
---

# helm-add

One-shot. Add a task to the kanbn board under Backlog.

---

## Usage

```
helm-add <title>: <body>
helm-add <title>
```

Text before the first colon is the title. Text after is the body (stored as a description, but the title is what appears in `.kanbn/index.md`). No colon means title only.

## Steps

### Step 1: Check board exists

If `.kanbn/index.md` does not exist, stop and tell the user to run `helm-setup` first.

### Step 2: Parse input

Split the argument on the first `:` character.

- Left side (trimmed) → task title
- Right side (trimmed) → task description (may be empty)

### Step 3: Add to board

Read `.kanbn/index.md`. Add `- <title>` as a new list item under the `## Backlog` heading (before the next `##` heading or end of file).

### Step 4: Report

```
Added: <title>
```
