---
name: mill-spawn
description: Add a task to tasks.md and create a worktree for it in one command.
---

# mill-spawn

One-shot. Add a task with `[spawn]` marker to `tasks.md`, commit, then call `spawn_task.py` to claim it and create a worktree.

For tasks.md file format details, see `plugins/mill/doc/formats/tasksmd.md`.

---

## Usage

```
mill-spawn <title>: <body>
mill-spawn <title>
```

Text before the first colon is the title. Text after is the body (description). No colon means title only.

---

## Steps

### Step 1: Check tasks.md exists

If `tasks.md` does not exist in the project root (the working directory where `_millhouse/` lives), stop and tell the user to run `mill-setup` first.

### Step 2: Parse input

Split the argument on the first `:` character.

- Left side (trimmed) -> task title
- Right side (trimmed) -> task description (may be empty)

### Step 3: Add task with spawn marker

Read `tasks.md`. Append a new task block at the end of the file with the `[spawn]` marker:

If no description:

```markdown
## [spawn] <Title>
```

If description provided:

```markdown
## [spawn] <Title>
- <Description>
```

### Step 4: Validate

Validate `tasks.md` per `doc/modules/validation.md` (tasks.md structural rules). If validation fails, report the issue to the user and stop.

### Step 5: Commit and push

```bash
git add tasks.md
git commit -m "task: spawn <title>"
git push
```

### Step 6: Call spawn_task.py

Locate `spawn_task.py` using three-tier resolution:

1. **Forwarding wrapper**: `_millhouse/mill-spawn.py` (written by `mill-setup`, resolves the plugin-cache path at runtime)
2. **Plugin source** (works in the millhouse repo itself): `<repo-root>/plugins/mill/scripts/spawn_task.py`
3. **Plugin cache** (works in any repo with mill plugin installed): `~/.claude/plugins/cache/millhouse/mill/<latest-version>/scripts/spawn_task.py`

Run via bash:

```bash
python "<resolved-path>"
```

The script reads the first `## [>] ` task from `tasks.md`, claims it (removes the task block, commits), creates the worktree via the Python `worktree.py` entrypoint (passing `WorktreeName` and `BranchName`), writes `_millhouse/task/status.md` in the new worktree, and writes a child registry entry to the parent's `_millhouse/children/` directory and a junction at `_millhouse/children/<slug>/` pointing to the new worktree's `_millhouse/task/`. The `task/`, `children/`, and `scratch/` folders are excluded from copy-on-spawn. Like all of `_millhouse/`, these folders are gitignored — registry entries and task state are local to each clone/worktree.

### Step 7: Report

Report the worktree path and branch name from the script output. The last line of stdout is the project path.

```
Spawned: <title>
  Branch: <branch-name>
  Path: <project-path>
```
