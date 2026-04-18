---
name: mill-cleanup
description: Clean up merged, abandoned, and stale worktrees, branches, and task entries.
---

# mill-cleanup

Single source of truth for removing merged, abandoned, and stale git state. `mill-merge` and
`mill-abandon` complete wiki cleanup before removing the junction — `mill-cleanup` handles leftover
worktrees, branches, orphan directories, and stale checkpoints. Run from the parent worktree after
the user has closed terminals and VS Code in any child worktrees.

Cleanup operates without per-item confirmation for clearly-flagged categories. If it encounters a
locked worktree (uncommitted work, OS file lock), it skips with a warning.

---

## Entry

Invoke `wiki.sync_pull(cfg)` on entry before reading any wiki state.

Verify this is the main worktree:
```bash
git rev-parse --show-toplevel
git worktree list --porcelain
```
If NOT the main worktree, stop: "mill-cleanup must be run from the main worktree."

Load config via `millpy.core.config.load_merged(shared_path, local_path)`.

---

## Junction safety

**Hard constraint:** Any code that removes a reparse point MUST use `(Get-Item $path).Delete()`.
NEVER use `Remove-Item -Recurse -Force` on a reparse-point path — it follows the junction and
deletes the TARGET directory's contents. Catastrophic data loss.

**Detection pattern:**
```powershell
$item = Get-Item $path -ErrorAction SilentlyContinue
if ($item -and $item.Attributes.ToString().Contains("ReparsePoint")) {
    $item.Delete()  # Safe: deletes only the reparse point
} else {
    Remove-Item $path -Recurse -Force  # Only for real directories
}
```

---

## Steps

mill-cleanup runs: **Phase 1: Detection** (read-only scan), **Phase 2: Execution** (actions),
**Phase 3: Report**.

### Phase 1: Detection

Build a cleanup set by scanning. Collect candidates with category, branch, worktree path,
and task slug. Deduplicate by branch and slug.

#### Scan 1: Wiki active directories

```python
wiki.sync_pull(cfg)
```

Enumerate `<wiki-clone>/active/*/` directories. Each entry is an authoritative active-task record.

For each active `<slug>`:
- Check if `git worktree list --porcelain` includes a worktree for the matching branch
  (`<branch-prefix>/<slug>` or `<slug>` when no prefix is configured).
- Read `.mill/active/<slug>/status.md` (via the wiki clone, not the junction) and extract `phase:`.

Categories:
- **`phase: complete` + worktree present** → candidate for merged cleanup.
- **`phase: complete` + no worktree** → orphaned active directory; delete from wiki.
- **No worktree present** → "active with no worktree". User can choose:
  - `mill-resume` (re-attach worktree)
  - `mill-abandon` (delete wiki state)
  - Skip (leave for later)

#### Scan 2: Home.md consistency check

Parse `Home.md` via `tasks_md.resolve_path(cfg)` + `tasks_md.parse`. Collect all `[active]` entries.

For each `[active]` entry in Home.md:
- If `<wiki-clone>/active/<slug>/` does NOT exist → flag as inconsistency:
  `Home.md says '<slug>' is [active] but wiki/active/<slug>/ does not exist.`
  (Closes issue #45.)

For each `<wiki-clone>/active/<slug>/` directory:
- If no matching `[active]` entry in Home.md → flag as inconsistency:
  `wiki/active/<slug>/ exists but Home.md has no [active] entry for it.`

Report inconsistencies to the user at Phase 3. Do NOT auto-fix them — they require human judgment.

#### Scan 3: Worktrees with no active wiki directory

Run `git worktree list --porcelain`. For each worktree other than the main one:
- Derive slug from the branch name.
- If `<wiki-clone>/active/<slug>/` does NOT exist AND the worktree has no `.mill/` junction:
  the worktree is a stray (created outside mill). Flag as orphan for user review.

#### Scan 4: Orphan worktree directories

Derive worktrees container: `<parent-of-repo-root>/<reponame>.worktrees/`.

Scan for subdirectories not listed in `git worktree list` output. Add each as an orphan.

Hub-layout skip: if a `.bare` directory exists at `<parent-of-repo-root>/.bare`, scan the hub root
directly for subdirectories not in `git worktree list`.

#### Scan 5: Stale checkpoint branches

Run `git branch --list 'mill-checkpoint-*'`. For each:
- If the underlying branch no longer exists AND no live worktree references it → mark for deletion.

### Phase 2: Execution

#### Action 1: Remove completed worktrees

For each worktree in the cleanup set with `phase: complete`:
1. Verify no uncommitted changes: `git -C <path> status --porcelain`. If non-empty, skip with warning.
2. Try `git worktree remove <path>`.
3. If locked directory error — **Windows:** if `handle.exe` (Sysinternals) is on PATH, run
   `handle.exe <path>` and surface the process names. Otherwise:
   `Directory locked. Close the process holding it (VS Code, a terminal) and re-run.`
   **POSIX:** if `lsof` is on PATH, run `lsof +D <path>` to list processes. Otherwise:
   `Directory locked. Close the process holding it and re-run.`
   (Closes issue #46.)
4. If removal fails for other reasons, retry with `git worktree remove --force <path>`.

#### Action 2: Delete local branches

For each branch from completed/orphaned entries:
```bash
git branch -D <branch>
```

#### Action 3: Delete remote branches

For each completed entry whose remote branch still exists:
```bash
git push origin --delete <branch>
```

#### Action 4: Delete stale checkpoint branches

```bash
git branch -D mill-checkpoint-<name>
```

#### Action 5: Remove orphan directories

Remove each orphan directory identified in Scan 4.

#### Action 6: Delete orphaned wiki active directories

For each orphaned active directory (Scan 1: `phase: complete` + no worktree, or inconsistency
confirmed as safe to delete):
```python
wiki.write_commit_push(cfg, [f"active/{slug}/"], f"task: cleanup orphaned {slug}")
```

#### Action 7: Regenerate sidebar (if any wiki changes occurred)

```bash
PYTHONPATH=<SCRIPTS_DIR> python -m millpy.entrypoints.regenerate_sidebar
```

#### Action 8: git worktree prune

```bash
git worktree prune
```

#### Action 9: Remove empty container directory

If `.worktrees/` container is now empty after Actions 1 and 5, `rmdir` it.

### Phase 3: Report

```
Cleanup complete.
  Worktrees removed:      N
  Branches deleted:       N local, N remote
  Checkpoint branches:    N
  Orphan directories:     N
  Wiki active dirs:       N removed

Inconsistencies (manual review needed):
  - Home.md says '<slug>' is [active] but wiki/active/<slug>/ does not exist.
  - wiki/active/<slug>/ exists but Home.md has no [active] entry for it.

Skipped (with warnings):
  - <item>: <reason>
```

If nothing found: "No cleanup needed. Repository is in a clean state."

---

## Board Updates

Cleanup does NOT write to Home.md directly (no phase marker changes). It only removes orphaned
active directories and regenerates the sidebar when active dirs are removed.

Home.md `[active]` → `[done]` transitions happen in `mill-merge`. `[active]` marker removal
happens in `mill-abandon`. mill-cleanup only detects inconsistencies between the two.
