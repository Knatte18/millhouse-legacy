---
name: mill-abandon
description: Mark a worktree task as abandoned. Captures abandon protocol and updates task status; git cleanup is deferred to mill-cleanup.
---

# mill-abandon

Release a task without marking it `[abandoned]`. The marker is cleared entirely, returning the task
to the pickable pool. If you want to permanently remove the task from Home.md, delete the entry
manually.

**Abandon does NOT mark the task `[abandoned]`. The `[active]` marker is removed so the task
becomes pickable again. We no longer use `[abandoned]` as a phase marker.**

The rationale: deleting a worktree while VS Code or a terminal still holds file handles causes lock
errors. Splitting into two commands (mark-released now, cleanup later from parent) avoids this.

---

## Entry

Invoke `wiki.sync_pull(cfg)` on entry before reading any wiki state.

Load config via `millpy.core.config.load_merged(shared_path, local_path)`.

Derive slug via `paths.slug_from_branch(cfg)`.

Verify this is a worktree (not the main repo). If the current directory is the main worktree:
stop: "mill-abandon must be run from a worktree, not the main repo."

Verify mill management: read `.mill/active/<slug>/status.md`. If absent or missing `task:`/`phase:`,
stop: "This worktree is not managed by mill (no status.md). Use `git worktree remove` manually."

Read current branch:
```bash
git branch --show-current
```

Read parent branch from config (`git.parent-branch`) or status.md `parent:` field.

---

## Steps

### 1. Check for uncommitted work

```bash
git status --porcelain
```

If uncommitted changes exist, warn:
> "This worktree has uncommitted changes. Abandon anyway?"

### 2. Check for unmerged commits

```bash
git log <parent-branch>..HEAD --oneline
```

If unmerged commits exist, warn:
> "This worktree has N commit(s) not merged to `<parent-branch>`."

### 3. Require confirmation

> "Type 'abandon' to confirm, or anything else to cancel."

Never auto-abandon. Never skip confirmation.

### 4. Acquire wiki lock

```python
wiki.acquire_lock(cfg, slug)
```

### 5. Clear `[active]` marker in Home.md

1. Read `Home.md` via `tasks_md.resolve_path(cfg)` + `tasks_md.parse`.
2. Find the entry whose `slugify(display_name)` matches the current slug.
3. Verify the entry's `phase` is `active`. If it is anything else, halt:
   `mill-abandon only applies to [active] tasks. This entry has phase: <phase>.`
4. Remove the phase marker entirely (set `phase = None`). The task becomes unmarked — pickable.
5. Render via `tasks_md.render`. Call `tasks_md.write_commit_push(cfg, rendered, f"task: abandon {slug}")`.

### 6. Delete active task directory from wiki

1. Remove `<wiki-clone>/active/<slug>/` via `rm -rf`.
2. Commit via `wiki.write_commit_push(cfg, [f"active/{slug}/"], f"task: abandon {slug} (delete state)")`.

### 7. Regenerate sidebar

```bash
PYTHONPATH=<SCRIPTS_DIR> python -m millpy.entrypoints.regenerate_sidebar
```

### 8. Release wiki lock

```python
wiki.release_lock(cfg)
```

Release happens in `finally` — runs on both success and error paths after Step 4.

### 9. Remove .mill/ junction

```python
from millpy.core.junction import remove
from millpy.core.paths import project_dir
remove(project_dir() / ".mill")
```

### 10. Optional worktree cleanup

If the user did NOT pass `--keep-worktree` (default: clean up):

Resolve the parent worktree path from `git worktree list --porcelain`.

```bash
git -C <parent-path> worktree remove --force <child-worktree-path>
git -C <parent-path> branch -d <child-branch>
```

If removal fails (locked directory): surface platform-aware hint (see mill-cleanup for
`handle.exe`/`lsof` diagnostic). Tell user to close the directory and re-run.

With `--keep-worktree`: skip Steps 9 and 10. The worktree remains with no `.mill/` junction.

### 11. Report

> "Task released. The `[active]` marker has been cleared — the task is pickable again.
> If you want to permanently remove it, delete the entry from Home.md."

---

## Board Updates

Home.md changes via `tasks_md.write_commit_push` (with wiki lock held).

`[active]` marker is removed entirely (not changed to `[abandoned]`). No `[abandoned]` phase.

Active task directory deleted from wiki at Step 6.

Phase transitions via `status_md.append_phase` are NOT called at abandon — the active directory
is deleted entirely, so there is no status.md to update after Step 6.
