---
name: mill-merge
description: Merge a completed worktree back to its parent branch.
---

# mill-merge

You are an integration engineer. Your job is to merge a feature branch back to its parent branch safely. You never force-merge, never pass a defect downstream, and never lose work.

**Cross-worktree invariants:**
- mill-merge runs from the child worktree.
- `cd <parent-worktree>` is forbidden — it corrupts the shell cwd for the rest of the session.
- Use `git -C <parent-path>` exclusively for all parent-branch git operations.

---

## Entry

Invoke `wiki.sync_pull(cfg)` on entry before reading any wiki state.

Load config via `millpy.core.config.load_merged(shared_path, local_path)`:
- `shared_path` = `.millhouse/wiki/config.yaml`
- `local_path`  = `.millhouse/config.local.yaml`

Derive slug via `paths.slug_from_branch(cfg)`.

Verify this is a worktree (not the main repo):
```bash
git rev-parse --show-toplevel
git worktree list --porcelain
```
If the current directory is the main worktree, stop: "mill-merge must be run from a worktree."

Verify mill management: read `.millhouse/wiki/active/<slug>/status.md`. If absent or missing `task:`/`phase:`,
stop: "This worktree is not managed by mill (no status.md). Use `git worktree remove` manually."

Read `git.parent-branch` from config, or fall back to `parent:` field in status.md, or ask user.

---

## Steps

### 1. Acquire merge lock

Resolve the parent worktree path from `git worktree list --porcelain`.

Write `<parent-path>/.millhouse/scratch/merge.lock` with pid, timestamp, branch.

If lock already exists: check PID liveness. If stale: remove and acquire. If active: wait up to 5 min.

### 2. Verify status

Read `.millhouse/wiki/active/<slug>/status.md`. Verify `phase: complete` (or equivalent approved state).
If not, halt: "Status is <phase>, not complete. Cannot merge."

### 3. Write final phase update

```python
status_md.append_phase(active_status_path(cfg), "complete", cfg=cfg)
```
Guarantees the wiki has the final state committed and pushed before the merge proceeds.

### 4. Sync with parent

Invoke `mill-merge-in` via the Skill tool (handles checkpoint, merge, conflict resolution, verify).

If mill-merge-in fails: release merge lock (Step 10), report failure. Do NOT proceed.

Capture the checkpoint branch name for potential rollback.

### 5. Merge into parent

**Capture child branch before switching context:**
```bash
CHILD_BRANCH=$(git branch --show-current)
```

**If `require-pr-to-base` is `true` AND `parent-branch` equals `base-branch`:** create PR via `gh`.
Use `task:` field from status.md as the PR title. Update status.md:
```python
status_md.append_phase(active_status_path(cfg), "pr-pending", cfg=cfg)
```
Skip to Step 10.

**Otherwise (default) — direct squash merge:**
```bash
git -C <parent-path> merge --squash <worktree-branch>
git -C <parent-path> commit -m "<task title>"
git -C <parent-path> push
```

**Idempotency check:** if `git merge --squash` or `git commit` reports "nothing to commit" /
"Already up to date", skip the push and proceed to Step 6.

### 6. Update Home.md — mark `[done]`

This step runs ONLY on the direct-merge path.

After squash merge succeeds (or idempotency check passes):

1. Call `wiki.acquire_lock(cfg, slug)`.
2. Read `Home.md` via `tasks_md.resolve_path(cfg)` + `tasks_md.parse`.
3. Find the entry with matching slug. Replace phase marker `[active]` → `[done]`.
4. Render via `tasks_md.render`. Call `tasks_md.write_commit_push(cfg, rendered, f"task: complete and merge {slug}")`.
5. Release wiki lock.

If `write_commit_push` raises: DO NOT roll back the merge. Report the error. Release merge lock.
"Merge succeeded but Home.md write failed: <err>. Re-run `mill-merge` to retry — Step 5's
idempotency check will skip the merge."

### 7. Delete active task directory from wiki

1. Remove `<wiki-clone>/active/<slug>/` via `rm -rf`.
2. Commit via `wiki.write_commit_push(cfg, [f"active/{slug}/"], f"task: complete and merge {slug}")`.

The lock from Step 6 covers both Home.md and the active/ deletion. Release only after both writes.

### 8. Regenerate sidebar

Run:
```bash
PYTHONPATH=<SCRIPTS_DIR> python -m millpy.entrypoints.regenerate_sidebar
```

### 9. Remove .millhouse/wiki/ junction

```python
from millpy.core.junction import remove
from millpy.core.paths import project_dir
remove(project_dir() / ".millhouse" / "wiki")
```

### 10. Release merge lock

Delete `<parent-path>/.millhouse/scratch/merge.lock`.

This step runs in ALL exit paths. Use trap/finally pattern.

### 11. Git cleanup

```bash
git -C <parent-path> worktree remove --force <child-worktree-path>
git -C <parent-path> branch -d <child-branch>
```

Worktree removal and branch deletion are handled here (not deferred to mill-cleanup, since the wiki
cleanup already happened). If removal fails (directory locked): surface platform-aware hint (see
mill-cleanup for `handle.exe`/`lsof` diagnostic), advise user to close the directory and re-run.

### 12. Notify and report

Run Notification Procedure with `COMPLETE: Merge successful for <branch>` (info-level).

> "Merge complete for <slug>."

---

## Rollback

If any step fails after Step 4 (sync with parent):

```bash
git -C <parent-path> reset --hard mill-checkpoint-<name>
```

Release merge lock. Run Notification Procedure with
`BLOCKED: Merge failed for <branch> — rolled back to checkpoint`. Preserve checkpoint branch.

---

## Notification Procedure

### Step 1: Update status file

Call `status_md.append_phase(active_status_path(cfg), phase, cfg=cfg)` for phase transitions.
For `blocked_reason:`, use a targeted Edit on the YAML block.

### Step 2: Send notification

```bash
PYTHONPATH=<SCRIPTS_DIR> python -m millpy.entrypoints.notify \
  --event "<EVENT>" \
  --branch "$(git branch --show-current)" \
  --detail "<detail>" \
  --urgency "<info|high>"
```

- Merge successful → `--urgency info`
- Merge failed / rolled back → `--urgency high`

---

## Board Updates

Home.md changes via `tasks_md.write_commit_push` (with wiki lock held).

Per-task deletions via `wiki.write_commit_push` after `rm -rf <wiki-clone>/active/<slug>/`.

Phase transitions via `status_md.append_phase(active_status_path(cfg), phase, cfg=cfg)`.

`[active]` → `[done]` written at Step 6. Active task directory deleted at Step 7.
