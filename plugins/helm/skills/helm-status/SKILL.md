---
name: helm-status
description: Dashboard showing all active worktrees and their state.
---

# helm-status

Dashboard. No arguments.

Shows board summary, current status, and worktree overview. Also cleans up stale worktrees.

---

## Steps

### Step 1: Read the board

Read `.kanban.md` from the repo root. If it does not exist, stop and tell the user to run `helm-setup` first.

Parse the file:
- `##` headings are columns (e.g. Backlog, In Progress, Done, Blocked).
- `###` headings are tasks within columns. A task heading may include a `[phase]` suffix (e.g. `### Fix bug [implementing]`).

Count tasks per column. For columns with tasks that have a `[phase]` suffix in their heading, also count tasks per phase within that column.

### Step 2: Read current status

Read `_helm/scratch/status.md` if it exists. Extract:
- `phase:` — current workflow phase
- `plan:` — path to plan file (if any)
- `task:` — current task name (if any)

If a plan file path is present and the file exists, read the plan to count total steps (lines matching `### Step`) and completed steps (based on git log matching `Commit:` messages from the plan).

### Step 3: Clean up stale worktrees

Run `git worktree list --porcelain`. For each worktree (skip the main one):
1. Check if the worktree's `_helm/scratch/status.md` has `phase: complete`.
2. Check if the worktree directory is still open in VS Code: `test -f <worktree-path>/.vscode-server` or check if any process holds a lock. In practice, just try `git worktree remove <path>` — if it fails (directory locked), skip it silently.
3. If phase is complete and removal succeeds: delete the local branch (`git branch -D <branch>`) and the remote branch (`git push origin --delete <branch>` if it was pushed). Report: `Cleaned up: <branch>`.

Run `git worktree prune` to remove any remaining stale entries (directories deleted manually).

### Step 4: Read worktrees

Run `git worktree list`. Parse the output — each line has: `<path> <hash> [<branch>]`.

Skip the main worktree (the first entry). For each additional worktree:
1. Extract branch name from the `[branch]` part.
2. Try to read `<worktree-path>/_helm/scratch/status.md` for that worktree's phase, step progress, and `parent:` field.
3. Determine parent branch from the `parent:` field in status.md. If not present, fall back to `main`.

### Step 5: Display dashboard

Print the dashboard. Use this exact format:

```
Board (.kanban.md):
  Backlog:       N tasks
  In Progress:   N tasks (details per phase if present)
  Done:          N tasks
  Blocked:       N tasks
```

Only show columns that exist in the board. For In Progress, if tasks have `[phase]` suffixes in their headings, show a parenthetical breakdown, e.g. `2 tasks (1 implementing, 1 reviewing)`.

If `_helm/scratch/status.md` exists and has a phase that is not `complete`:

```
Current:
  Task:   <task name or "unknown">
  Phase:  <phase>
  Plan:   <plan path or "none">
  Steps:  N/M completed (or "no plan" if no plan file)
```

If there are worktrees beyond the main one:

```
Worktrees:
  <branch>  [<phase>]  <progress>  parent: <parent>
```

Where:
- `<branch>` is the worktree branch name, left-aligned
- `<phase>` comes from that worktree's status.md, or `unknown` if not readable
- `<progress>` is `N/M steps` if a plan exists, otherwise `no plan`
- `<parent>` is the inferred parent branch

If there are no extra worktrees, show:

```
Worktrees:
  (none)
```

### Example output

```
Board (.kanban.md):
  Backlog:       2 tasks
  In Progress:   1 task
  Blocked:       0 tasks
  Done:          1 task

Current:
  Task:   Implement helm-status skill
  Phase:  implementing
  Steps:  2/5 completed

Worktrees:
  (none)
```
