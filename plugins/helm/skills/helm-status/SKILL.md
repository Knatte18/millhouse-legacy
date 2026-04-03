---
name: helm-status
description: Dashboard showing all active worktrees and their state.
---

# helm-status

Dashboard. Read-only. No arguments.

Shows board summary, current status, and worktree overview.

---

## Steps

### Step 1: Read the board

Read `.kanban.md` from the repo root. If it does not exist, stop and tell the user to run `helm-setup` first.

Parse the file:
- `##` headings are columns (e.g. Backlog, In Progress, Done, Blocked).
- `###` headings are tasks within columns.
- Each task may have `- phase: <value>` metadata.

Count tasks per column. For columns with tasks that have `- phase:` metadata, also count tasks per phase within that column.

### Step 2: Read current status

Read `_helm/scratch/status.md` if it exists. Extract:
- `phase:` — current workflow phase
- `plan:` — path to plan file (if any)
- `task:` — current task name (if any)

If a plan file path is present and the file exists, read the plan to count total steps (lines matching `### Step`) and completed steps (based on git log matching `Commit:` messages from the plan).

### Step 3: Read worktrees

Run `git worktree list`. Parse the output — each line has: `<path> <hash> [<branch>]`.

Skip the main worktree (the first entry). For each additional worktree:
1. Extract branch name from the `[branch]` part.
2. Try to read `<worktree-path>/_helm/scratch/status.md` for that worktree's phase, step progress, and `parent:` field.
3. Determine parent branch from the `parent:` field in status.md. If not present, fall back to `main`.

### Step 4: Display dashboard

Print the dashboard. Use this exact format:

```
Board (.kanban.md):
  Backlog:       N tasks
  In Progress:   N tasks (details per phase if present)
  Done:          N tasks
  Blocked:       N tasks
```

Only show columns that exist in the board. For In Progress, if tasks have phase metadata, show a parenthetical breakdown, e.g. `2 tasks (1 implementing, 1 reviewing)`.

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
