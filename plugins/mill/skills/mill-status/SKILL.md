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

Load `_millhouse/config.yaml`. Resolve tasks.md via `millpy.tasks.tasks_md.resolve_path(cfg)`. If resolution raises (config missing or tasks worktree not found), note the error, print a one-line warning, and show `Tasks source: not configured` in the dashboard; continue rendering worktree state so the dashboard still has value.

Read tasks.md via `tasks_md.parse(resolve_path(cfg))`. For each `## ` heading, categorize into the following buckets:
- No `[phase]` marker → **Unclaimed**
- `[s]` → **Ready**
- `[active]` → **Active**
- `[completed]` → **Completed**
- `[done]` → **Done**
- `[abandoned]` → **Abandoned**

Read the YAML code block in `_millhouse/task/status.md` if it exists. Extract `phase:`, `task:`, `plan:`, and the timeline entries from the ` ```text ``` ` fence in the `## Timeline` section.

### Step 2: Read current status

Read the YAML code block in `_millhouse/task/status.md` if it exists. Extract:
- `phase:` — current workflow phase
- `plan:` — path to plan file (if any)
- `task:` — current task name (if any)

If a plan file path is present and the file exists, read the plan to count total steps (lines matching `### Step`) and completed steps (based on git log matching `Commit:` messages from the plan).

### Step 3: Build worktree tree

Read `tasks.worktree-path` from `_millhouse/config.yaml`. When iterating `git worktree list --porcelain`, filter out any worktree whose path (normalized to forward slashes) matches the configured tasks-worktree-path — it is not a feature worktree and must not appear in the tree render.

1. Run `git worktree list --porcelain` to get all worktrees with their branches and paths.
2. For each worktree, read `_millhouse/children/` folder if it exists. Collect ALL `.md` files (active, merged, and abandoned entries). Parse YAML frontmatter for `branch:` and `status:` fields.
3. For each worktree, read the YAML code block in `_millhouse/task/status.md` for phase and step progress. If a plan file path is present and the file exists, count total steps (`### Step` lines) and completed steps (via git log).
4. Build a tree structure:
   - The main worktree is the root node.
   - For each worktree, its children are the entries in its `_millhouse/children/` folder.
   - For each **active** child (registry `status: active` or `status: pr-pending`):
     1. Derive the slug from the registry file's stem (strip the leading `<timestamp>-` prefix).
     2. **Primary source:** try to read `<parent>/_millhouse/children/<slug>/status.md` (via the junction). If the read succeeds, use the YAML code block for phase/progress.
     3. **Fallback:** if the junction read throws an exception (dangling junction — target missing or junction missing): fall back to `git worktree list --porcelain` lookup, reading `<child>/_millhouse/task/status.md` directly.
     4. **Both fail:** display `<slug>  [target missing — run mill-cleanup]` for that entry and continue rendering other children.
   - For **merged/abandoned** children, show them under their parent with their registry status. No live worktree lookup needed.
   - Recurse: if a child worktree has its own `_millhouse/children/`, include its children as grandchildren, and so on.

### Step 4: Detect stale state (for cleanup suggestion)

Scan for any of the following. If any are found, remember to emit a cleanup suggestion at the bottom of the dashboard in Step 5:

- Children entries in `_millhouse/children/*.md` with `status: merged`, `status: abandoned`, or `status: complete`.
- Worktrees (from `git worktree list --porcelain`) whose `_millhouse/task/status.md` YAML code block has `phase: complete`.
- Orphan directories in `<parent-of-repo-root>/<reponame>.worktrees/` (non-hub layout): subdirs not in `git worktree list` output. Skip this check if hub layout is detected (a `.bare` directory exists at `<parent-of-repo-root>/.bare`) — hub-layout orphan detection is handled by `mill-cleanup` itself.
- `[done]` or `[abandoned]` task markers in `tasks.md`. Do NOT flag `[completed]` — it is a normal in-progress state ("work done, not yet merged").

This is a read-only detection. No state is modified; this skill does not run cleanup actions.

### Step 5: Display dashboard

Print the dashboard. Use this exact format:

```
Tasks source: <absolute path to tasks worktree>
Tasks (tasks.md):
  Unclaimed:     N tasks
  In-progress:   N tasks
```

When Y (`[completed]`) > 0, the In-progress line gains an inline breakdown: `In-progress:   N tasks     (X active, Y completed)`. If Y = 0, render without the breakdown (matches current output).

If there are in-progress tasks, list them (both `[active]` and `[completed]` entries):

```
Active tasks:
  [active]     Task A
  [completed]  Task B
```

Source of truth for phase: `phase:` field in the YAML code block of `_millhouse/task/status.md`.

If `_millhouse/task/status.md` exists and has a `## Timeline` section (read entries from within the ` ```text ``` ` fence):

```
Timeline (_millhouse/task/status.md):
  discussing              2026-04-08T10:23:15Z
  discussed               2026-04-08T10:45:00Z
  implementing            2026-04-08T11:00:00Z
```

Show all timeline entries from the `## Timeline` section, one per line. If status.md does not exist or has no `## Timeline` section, show `Timeline: (none)`.

If the YAML code block in `_millhouse/task/status.md` has a phase that is not `complete`:

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
      add-caching  [discussed]
    feature-x  [planned]
```

Where:
- Each level is indented by 2 additional spaces
- Active children with live worktrees show their phase and progress from the YAML code block in `status.md`
- Active children with unresolvable state show `[target missing — run mill-cleanup]`
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
Tasks source: /home/user/code/myrepo.worktrees/tasks
Tasks (tasks.md):
  Unclaimed:     2 tasks
  In-progress:   2 tasks     (1 active, 1 completed)

Active tasks:
  [active]     Implement mill-status skill
  [completed]  Add OAuth Support

Timeline (_millhouse/task/status.md):
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
      add-caching  [discussed]
    feature-x  [planned]
```
