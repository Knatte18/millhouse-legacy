---
name: mill-status
description: Dashboard showing all active worktrees and their state.
---

# mill-status

Dashboard. No arguments.

Shows task overview, current status, and worktree overview. Also cleans up stale worktrees.

---

## Steps

### Step 1: Read tasks.md and status

Resolve the repo root via `git rev-parse --show-toplevel`. Check that `tasks.md` exists at the repo root. If it does not exist, stop and tell the user to run `mill-setup` first.

Read `tasks.md`. For each `## ` heading, categorize:
- Headings without a `[phase]` marker -> unclaimed tasks
- Headings with a `[phase]` marker -> active tasks (extract the phase name)

Read `_millhouse/scratch/status.md` if it exists. Extract `phase:`, `task:`, `plan:`, and the `## Timeline` section.

### Step 2: Read current status

Read `_millhouse/scratch/status.md` if it exists. Extract:
- `phase:` — current workflow phase
- `plan:` — path to plan file (if any)
- `task:` — current task name (if any)

If a plan file path is present and the file exists, read the plan to count total steps (lines matching `### Step`) and completed steps (based on git log matching `Commit:` messages from the plan).

### Step 3: Clean up stale worktrees

Run `git worktree list --porcelain`. For each worktree (skip the main one):
1. Check if the worktree's `_millhouse/scratch/status.md` has `phase: complete`.
2. Check if the worktree directory is still open in VS Code: `test -f <worktree-path>/.vscode-server` or check if any process holds a lock. In practice, just try `git worktree remove <path>` — if it fails (directory locked), skip it silently.
3. If phase is complete and removal succeeds: delete the local branch (`git branch -D <branch>`) and the remote branch (`git push origin --delete <branch>` if it was pushed). Report: `Cleaned up: <branch>`.

Run `git worktree prune` to remove any remaining stale entries (directories deleted manually).

Check for orphaned worktree directories using layout-aware logic. Derive hub root: the parent directory of the repo root (`git rev-parse --show-toplevel`). Detect hub layout: `.bare` directory exists at `<hub-root>/.bare`.
- **Hub layout**: scan the hub root for subdirectories not in `git worktree list` output AND not `.bare`. These are orphans — delete them immediately without asking for confirmation. Report each deletion: `Cleaned up orphan: <dirname>`.
- **Non-hub layout**: skip orphan directory scanning entirely — no dedicated container directory exists, so scanning the parent directory would be overly broad.

### Step 4: Build worktree tree

1. Run `git worktree list --porcelain` to get all worktrees with their branches and paths.
2. For each worktree, read `_millhouse/children/` folder if it exists. Collect ALL `.md` files (active, merged, and abandoned entries). Parse YAML frontmatter for `branch:` and `status:` fields.
3. For each worktree, read `_millhouse/scratch/status.md` for phase and step progress. If a plan file path is present and the file exists, count total steps (`### Step` lines) and completed steps (via git log).
4. Build a tree structure:
   - The main worktree is the root node.
   - For each worktree, its children are the entries in its `_millhouse/children/` folder.
   - For each **active** child, check if a live worktree exists for that branch (match branch name against `git worktree list` output). If it does, read the child's live `_millhouse/scratch/status.md` for phase/progress. If no live worktree, show `[active — no worktree]`.
   - For **merged/abandoned** children, show them under their parent with their registry status. No live worktree lookup needed.
   - Recurse: if a child worktree has its own `_millhouse/children/`, include its children as grandchildren, and so on.

### Step 5: Display dashboard

Print the dashboard. Use this exact format:

```
Tasks (tasks.md):
  Unclaimed:     N tasks
  In-progress:   N tasks
```

If there are in-progress tasks, list them:

```
Active tasks:
  [discussing]     Task A
  [implementing]   Task B
```

Source of truth for phase: `phase:` field in `_millhouse/scratch/status.md`.

If `_millhouse/scratch/status.md` exists and has a `## Timeline` section:

```
Timeline (_millhouse/scratch/status.md):
  discussing              2026-04-08T10:23:15Z
  discussed               2026-04-08T10:45:00Z
  implementing            2026-04-08T11:00:00Z
```

Show all timeline entries from the `## Timeline` section, one per line. If status.md does not exist or has no `## Timeline` section, show `Timeline: (none)`.

If `_millhouse/scratch/status.md` exists and has a phase that is not `complete`:

```
Current:
  Task:   <task name or "unknown">
  Phase:  <phase>
  Plan:   <plan path or "none">
  Steps:  N/M completed (or "no plan" if no plan file)
```

Display the worktree tree with indentation showing parent-child relationships:

```
Worktrees:
  main
    hanf  [implementing]  3/5 steps
      fix-login-bug  [merged]
      add-caching  [discussing]
    feature-x  [planned]
```

Where:
- Each level is indented by 2 additional spaces
- Active children with live worktrees show their phase and progress from `status.md`
- Active children without live worktrees show `[active — no worktree]`
- Merged/abandoned children show their registry status (e.g., `[merged]`, `[abandoned]`)
- If a child's status is unreadable, show `[unknown]`
- If `_millhouse/children/` is missing for a node, that node simply shows no children

If there are no worktrees beyond main and main has no children:

```
Worktrees:
  main
```

### Example output

```
Tasks (tasks.md):
  Unclaimed:     2 tasks
  In-progress:   1 task

Active tasks:
  [implementing]   Implement mill-status skill

Timeline (_millhouse/scratch/status.md):
  discussing              2026-04-08T10:23:15Z
  discussed               2026-04-08T10:45:00Z
  implementing            2026-04-08T11:00:00Z

Current:
  Task:   Implement mill-status skill
  Phase:  implementing
  Steps:  2/5 completed

Worktrees:
  main
    hanf  [implementing]  3/5 steps
      fix-login-bug  [merged]
      add-caching  [discussing]
    feature-x  [planned]
```
