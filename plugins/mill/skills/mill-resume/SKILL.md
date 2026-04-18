---
name: mill-resume
description: Resume an active task from the wiki on another machine or after a fresh clone.
---

# mill-resume

One-shot. Finds an `[active]` task in `Home.md` that has no local worktree, then recreates the worktree from the remote branch and wiki state so the user can continue with `mill-go`.

**Sync invariant:** mill-resume MUST call `wiki.sync_pull(cfg)` on entry before reading any wiki state.

---

## Usage

```
mill-resume <slug>
mill-resume
```

If a slug is passed, resume that specific task. If no argument is provided, list resume candidates and let the user pick.

---

## Phases

### Phase 1: Verify setup

If `_millhouse/config.local.yaml` (or the legacy `_millhouse/config.yaml`) does not exist, stop and tell the user to run `mill-setup` first.

If the `.mill/` junction does not exist at cwd, stop and tell the user to run `mill-setup` first (the wiki junction is required to read task state).

### Phase 2: Sync wiki

Call `wiki.sync_pull(cfg)` to refresh the local wiki clone from remote. This ensures the task list reflects the current state across all machines and worktrees.

### Phase 3: Resolve the slug

**If a slug argument was passed:** use it directly. Skip to Phase 4.

**If no argument was passed:** read `Home.md` from `.mill/Home.md` and find resume candidates.

A resume candidate is an entry that:

1. Has an `[active]` phase marker in `Home.md`.
2. Does NOT already have a local worktree at `<worktrees-dir>/<slug>/` with a matching branch (`git branch --list <branch_name>` returns output).

Read `repo.branch-prefix` from config (if set). Derive `branch_name` for each slug: if prefix is set and non-empty, `branch_name = f"{prefix}/{slug}"`; otherwise `branch_name = slug`.

Present candidates as a numbered list:

```
Resume candidates:
  1) <slug-a>  (phase: implementing)
  2) <slug-b>  (phase: planned)
Pick a number:
```

The phase shown is from `.mill/active/<slug>/status.md` (read the `phase:` field from the YAML block). If status.md is missing, show `(phase: unknown)`.

If there are no candidates (all active tasks already have a local worktree), print:

```
No tasks to resume. All active tasks already have a local worktree.
```

and stop.

### Phase 4: Derive branch name

Given the slug (from argument or user pick), derive the full branch name:

- If `repo.branch-prefix` from config is set and non-empty: `branch_name = f"{prefix}/{slug}"`
- Otherwise: `branch_name = slug`

All subsequent git commands use `<branch_name>`, NOT `<slug>` directly.

### Phase 5: Pre-flight checks

**Check 1 — remote branch exists:**

```bash
git ls-remote --exit-code origin <branch_name>
```

If the remote branch does not exist, halt with:

```
No remote branch '<branch_name>' exists. The task is active but the feature branch was never pushed — resolve manually (abandon or push-first).
```

**Check 2 — wiki state exists:**

Check whether `.mill/active/<slug>/` exists in the local wiki clone.

If it does not exist, halt with:

```
Home.md lists '<slug>' as [active] but wiki has no state for it. Resolve manually: decide between mill-abandon (cleanup) or a fresh mill-spawn.
```

### Phase 6: Create worktree

```bash
git -C <git-root> worktree add <worktrees-dir>/<slug> <branch_name>
```

Where:
- `<git-root>` is `git rev-parse --show-toplevel` from cwd.
- `<worktrees-dir>` is `<git-root-parent>/<repo-name>.worktrees/`.

If the remote-tracking branch is not yet fetched, git will fetch it automatically. If `git worktree add` fails (branch already checked out elsewhere, disk error, etc.), report the error and stop.

### Phase 7: Copy `_millhouse/` from parent

Copy `_millhouse/` (excluding `task/`, `scratch/`, and `children/`) from the parent worktree (cwd) to the new worktree. This gives the new worktree the config and wrapper scripts without inheriting stale task state.

Also copy `_millhouse/config.local.yaml` from the parent to the new worktree if it exists.

This is the same copy step as `mill-spawn` — see `plugins/mill/scripts/millpy/entrypoints/spawn_task.py` for the canonical implementation.

### Phase 8: Create `.mill/` junction

Create a `.mill/` junction in the new worktree pointing at the same wiki clone as the parent:

```python
from millpy.core.junction import create as junction_create
junction_create(new_worktree / ".mill", wiki_clone_path)
```

### Phase 9: Read and report phase

Read `.mill/active/<slug>/status.md` from the wiki clone. Parse the `phase:` field from the YAML block.

### Phase 10: Regenerate sidebar

Invoke the `regenerate_sidebar` entrypoint to keep `_Sidebar.md` in sync:

```bash
PYTHONPATH=<scripts-dir> python -m millpy.entrypoints.regenerate_sidebar
```

The `[active]` entry is already present in `Home.md` — regenerating the sidebar ensures any proposals added while the task was paused are reflected.

### Phase 11: Report

Print:

```
Resumed task '<slug>' at phase: <phase>. Run mill-go to continue.
  Branch: <branch-name>
  Path:   <project-path>
```

If the current phase is a review phase (e.g. `plan-reviewing`, `reviewing`), also print:

```
Note: task is mid-review. mill-go will re-enter the current phase from its start (new review round; reviewer invocations are idempotent via timestamped filenames).
```

---

## Error Conditions

| Condition | Action |
|---|---|
| `_millhouse/config.local.yaml` missing | Stop, tell user to run `mill-setup` |
| `.mill/` junction missing | Stop, tell user to run `mill-setup` |
| `wiki.sync_pull` fails | Report error; do not proceed (stale state risk) |
| No remote branch for slug | Halt with manual-resolution message |
| No wiki state for slug | Halt with manual-resolution message |
| `git worktree add` fails | Report error with stderr |
| No resume candidates | Print "no tasks to resume" and stop |
