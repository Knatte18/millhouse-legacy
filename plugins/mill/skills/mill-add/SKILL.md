---
name: mill-add
description: Create a new task in tasks.md.
---

# mill-add

One-shot. Add a task to `tasks.md` on the orphan `tasks` branch.

For tasks.md file format details, see `plugins/mill/doc/formats/tasksmd.md`.

---

## How tasks.md is resolved

As of the orphan-`tasks`-branch change, `tasks.md` lives on a dedicated branch and is checked out at the path configured in `.millhouse/config.yaml` → `tasks.worktree-path`. This skill reads and writes that file exclusively via `millpy.tasks.tasks_md.resolve_path` + `write_commit_push`. Never run git commands against `tasks.md` in the current worktree.

---

## Usage

```
mill-add <title>: <body>
mill-add <title>
```

Text before the first colon is the title. Text after is the body. No colon means title only.

## Steps

### Step 1: Resolve tasks.md

Load `.millhouse/config.yaml` via `millpy.core.config.load`. Call `millpy.tasks.tasks_md.resolve_path(cfg)` to get the absolute path to tasks.md on the tasks worktree. If this raises `ConfigError` or `FileNotFoundError`, stop and tell the user: "Tasks worktree not found — run mill-setup first."

### Step 2: Parse input

Split the argument on the first `:` character.

- Left side (trimmed) -> task title
- Right side (trimmed) -> task description (may be empty)

### Step 3: Add task to tasks.md

Read the tasks worktree's tasks.md via the resolved path (`tasks_md.parse(tasks_md_path)`). Append a new task block at the end of the in-memory task list:

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

Validate `tasks.md` per `plugins/mill/doc/formats/validation.md` (tasks.md structural rules). If validation fails, report the issue to the user and stop.

### Step 5: Commit and push

Call `millpy.tasks.tasks_md.write_commit_push(cfg, rendered_content, f"task: add {title}")`. The helper handles the lock, write, add/commit/push, retries on non-FF, and raises on unrecoverable failures.

### Step 6: Report

```
Added: <title>
```
