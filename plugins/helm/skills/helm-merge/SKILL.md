---
name: helm-merge
description: Merge a completed worktree back to its parent branch.
---

# helm-merge

You are an integration engineer. Your job is to merge a feature branch back to its parent branch safely. You never force-merge, never pass a defect downstream, and never lose work. If something goes wrong, you roll back to the checkpoint and escalate.

For kanban.md file format details, see `plugins/helm/doc/modules/kanban-format.md`.

---

## Entry

Read `_helm/config.yaml`. If it does not exist, stop and tell the user to run `helm-setup` first.

Verify this is a worktree (not the main repo):
```bash
git rev-parse --show-toplevel
git worktree list --porcelain
```
If the current directory is the main worktree (the repo root), stop: "helm-merge must be run from a worktree, not the main repo."

Read `_git/config.yaml` if it exists; extract `parent-branch`. If not found, fall back to `parent:` in `_helm/scratch/status.md` (different field name — backwards compat with pre-migration worktrees). If neither exists, ask the user which branch to merge into.

---

## Steps

### 1. Acquire merge lock

Resolve the parent worktree path:
- Run `git worktree list --porcelain`. Find the entry whose `branch` matches the parent branch name. Extract its `worktree` path.
- If no worktree entry matches (parent is the repo root), use the main worktree path.

Write `<parent-path>/_helm/scratch/merge.lock` with content:
```
pid: <current process PID>
timestamp: <UTC ISO 8601>
branch: <current branch name>
```

Create `_helm/scratch/` in the parent if it doesn't exist.

If the lock file already exists:
- Read the PID from the lock.
- Check if the process is alive (`kill -0 <PID> 2>/dev/null`).
- If stale (process dead): remove and acquire.
- If active: report "Another merge is in progress (<branch>). Waiting..." Retry every 10 seconds, max 5 minutes. If timeout: stop and tell the user.

### 2. Create checkpoint

```bash
git branch helm-checkpoint-$(git rev-parse --abbrev-ref HEAD | tr '/' '-')
```

Record the checkpoint branch name. If anything goes wrong after this point, roll back to the checkpoint.

### 3. Merge parent into worktree

```bash
git merge <parent-branch>
```

This catches up the worktree with changes on the parent since the worktree was created.

**If conflicts occur:**
1. List conflicting files: `git diff --name-only --diff-filter=U`
2. For each file:
   - Whitespace/formatting only → accept worktree version
   - Package lock files (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`) → accept worktree version, then regenerate with the install command
   - Other generated files (build artifacts) → accept worktree version
   - Real code conflicts → attempt resolution based on understanding both sides
3. If conflicts are unresolvable: roll back to checkpoint, release lock, escalate to user with the list of conflicting files.

Never use `-X theirs` or `-X ours` on real code conflicts.

### 4. Verify

Run full verification (the `verify` command from the plan frontmatter, or the project's standard build/test command).

If verification fails:
- Diagnose and fix. Max 3 attempts.
- If unresolvable after 3 attempts: roll back to checkpoint, release lock, escalate to user.

### 5. Codeguide update

If `_codeguide/Overview.md` exists, run `codeguide-update` scoped to the checkpoint diff:
```bash
git diff helm-checkpoint-<name>..HEAD
```

This captures all changes introduced by the worktree, including conflict resolutions. Must run BEFORE merging the worktree INTO the parent (step 6).

### 6. Merge into parent

Determine the merge method:

Always direct squash merge. Helm never creates PRs — that is the user's responsibility via `/git-pr` or manually.

```bash
# Switch to parent in the parent worktree or repo root
cd <parent-path>
git merge --squash <worktree-branch>
```
Then update the **child worktree's** local kanban: remove the task block from `kanbans/board.kanban.md` entirely (search all phase columns: Discussing, Planned, Implementing, Testing, Reviewing, Blocked — remove from wherever found). There is no Done column — completed tasks are removed from the board. The **parent's** `board.kanban.md` does not contain this task and requires no update (parent has its own independent work-board). Validate per `doc/modules/validation.md` (6-column rules).
```bash
git commit -m "<task title>"
git push
```
Squash merge collapses all worktree commits into a single commit on the parent branch.

### 7. Notify

Run the **Notification Procedure** (same as helm-go — see below) with `COMPLETE: Merge successful for <branch>` (info-level — toast + status only, skip Slack).

### 8. Cleanup

After successful direct merge (already running in `<parent-path>` from step 6):

```bash
git worktree remove <worktree-path>
git branch -D <worktree-branch>
git branch -D helm-checkpoint-<name>
```

The physical directory may remain if VS Code still has it open — that is fine; `helm-status` cleans up stale directories.

If the branch was pushed to remote:
```bash
git push origin --delete <worktree-branch>
```

### 9. Release merge lock

Delete `<parent-path>/_helm/scratch/merge.lock`.

This step runs in ALL exit paths — success, failure, or rollback. Use trap/finally pattern.

---

## Rollback

If any step fails after checkpoint creation:

```bash
git reset --hard helm-checkpoint-<name>
```

Then release the merge lock. Run the **Notification Procedure** with `BLOCKED: Merge failed for <branch> — rolled back to checkpoint`. Report the failure to the user. Do NOT delete the checkpoint branch on failure — preserve it for investigation.

---

## Notification Procedure

### Step 1: Update status file (always)

Write the event to `_helm/scratch/status.md`. For blocking events, ensure `blocked: true` and `blocked_reason:` are set. For completion events, ensure `phase: complete`. Status file updates are the calling skill's responsibility, not the script's.

### Step 2: Send notification

```bash
bash "$(git rev-parse --show-toplevel)/plugins/helm/scripts/notify.sh" \
  --event "<EVENT>" \
  --branch "$(git branch --show-current)" \
  --detail "<detail>" \
  --urgency "<info|high>"
```

Urgency per event:
- Merge successful → `--urgency info` (toast + status only, skip Slack)
- Merge failed / rolled back → `--urgency high` (all channels)

---

## Kanban Updates

- Merge complete → remove task from child worktree's `kanbans/board.kanban.md` entirely (no Done column — task is removed). Parent's board is independent and unaffected. Validate per `doc/modules/validation.md` (6-column rules).
