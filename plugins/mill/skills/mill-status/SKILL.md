---
name: mill-status
description: Dashboard showing all active worktrees and their state.
---

# mill-status

Dashboard. No arguments.

Shows task overview, current status, and worktree overview. Read-only — if stale state is detected, it suggests running `mill-cleanup` but does not mutate git state itself.

---

## Steps

### Step 1: Read tasks.md and status

Check that `tasks.md` exists in the project root (the working directory where `_millhouse/` lives). If it does not exist, stop and tell the user to run `mill-setup` first.

Read `tasks.md`. For each `## ` heading, categorize:
- Headings without a `[phase]` marker -> unclaimed tasks
- Headings with a `[phase]` marker -> active tasks (extract the phase name)

Read the YAML code block in `_millhouse/scratch/status.md` if it exists. Extract `phase:`, `task:`, `plan:`, and the timeline entries from the ` ```text ``` ` fence in the `## Timeline` section.

### Step 2: Read current status

Read the YAML code block in `_millhouse/scratch/status.md` if it exists. Extract:
- `phase:` — current workflow phase
- `plan:` — path to plan file (if any)
- `task:` — current task name (if any)

If a plan file path is present and the file exists, read the plan to count total steps (lines matching `### Step`) and completed steps (based on git log matching `Commit:` messages from the plan).

### Step 3: Build worktree tree

1. Run `git worktree list --porcelain` to get all worktrees with their branches and paths.
2. For each worktree, read `_millhouse/children/` folder if it exists. Collect ALL `.md` files (active, merged, and abandoned entries). Parse YAML frontmatter for `branch:` and `status:` fields.
3. For each worktree, read the YAML code block in `_millhouse/scratch/status.md` for phase and step progress. If a plan file path is present and the file exists, count total steps (`### Step` lines) and completed steps (via git log).
4. Build a tree structure:
   - The main worktree is the root node.
   - For each worktree, its children are the entries in its `_millhouse/children/` folder.
   - For each **active** child, check if a live worktree exists for that branch (match branch name against `git worktree list` output). If it does, read the child's live `_millhouse/scratch/status.md` YAML code block for phase/progress. If no live worktree, show `[active — no worktree]`.
   - For **merged/abandoned** children, show them under their parent with their registry status. No live worktree lookup needed.
   - Recurse: if a child worktree has its own `_millhouse/children/`, include its children as grandchildren, and so on.

### Step 4: Detect stale state (for cleanup suggestion)

Scan for any of the following. If any are found, remember to emit a cleanup suggestion at the bottom of the dashboard in Step 5:

- Children entries in `_millhouse/children/*.md` with `status: merged`, `status: abandoned`, or `status: complete`.
- Worktrees (from `git worktree list --porcelain`) whose `_millhouse/scratch/status.md` YAML code block has `phase: complete`.
- Orphan directories in `<parent-of-repo-root>/<reponame>.worktrees/` (non-hub layout): subdirs not in `git worktree list` output. Skip this check if hub layout is detected (a `.bare` directory exists at `<parent-of-repo-root>/.bare`) — hub-layout orphan detection is handled by `mill-cleanup` itself.
- `[done]` or `[abandoned]` task markers in `tasks.md`.

This is a read-only detection. No state is modified; this skill does not run cleanup actions.

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

Source of truth for phase: `phase:` field in the YAML code block of `_millhouse/scratch/status.md`.

If `_millhouse/scratch/status.md` exists and has a `## Timeline` section (read entries from within the ` ```text ``` ` fence):

```
Timeline (_millhouse/scratch/status.md):
  discussing              2026-04-08T10:23:15Z
  discussed               2026-04-08T10:45:00Z
  implementing            2026-04-08T11:00:00Z
```

Show all timeline entries from the `## Timeline` section, one per line. If status.md does not exist or has no `## Timeline` section, show `Timeline: (none)`.

If the YAML code block in `_millhouse/scratch/status.md` has a phase that is not `complete`:

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
- Active children with live worktrees show their phase and progress from the YAML code block in `status.md`
- Active children without live worktrees show `[active — no worktree]`
- Merged/abandoned children show their registry status (e.g., `[merged]`, `[abandoned]`)
- If a child's status is unreadable, show `[unknown]`
- If `_millhouse/children/` is missing for a node, that node simply shows no children

If there are no worktrees beyond main and main has no children:

```
Worktrees:
  main
```

If any stale state was detected in Step 4, append this line at the very bottom of the dashboard output:

```
Stale state detected. Run `mill-cleanup` from the main worktree to clean up.
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
