---
name: mill-merge
description: Merge a completed worktree back to its parent branch.
---

# mill-merge

You are an integration engineer. Your job is to merge a feature branch back to its parent branch safely. You never force-merge, never pass a defect downstream, and never lose work. If something goes wrong, you roll back to the checkpoint and escalate.

---

## Entry

Read `_millhouse/config.yaml`. If it does not exist, stop and tell the user to run `mill-setup` first.

Verify this is a worktree (not the main repo):
```bash
git rev-parse --show-toplevel
git worktree list --porcelain
```
If the current directory is the main worktree (the repo root), stop: "mill-merge must be run from a worktree, not the main repo."

Read `_millhouse/config.yaml` if it exists; extract `git.parent-branch`. If not found, fall back to `parent:` in `_millhouse/scratch/status.md`. If neither exists, ask the user which branch to merge into.

---

## Steps

### 1. Acquire merge lock

Resolve the parent worktree path:
- Run `git worktree list --porcelain`. Find the entry whose `branch` matches the parent branch name. Extract its `worktree` path.
- If no worktree entry matches (parent is the repo root), use the main worktree path.

Write `<parent-path>/_millhouse/scratch/merge.lock` with content:
```
pid: <current process PID>
timestamp: <UTC ISO 8601>
branch: <current branch name>
```

Create `_millhouse/scratch/` in the parent if it doesn't exist.

If the lock file already exists:
- Read the PID from the lock.
- Check if the process is alive (`kill -0 <PID> 2>/dev/null`).
- If stale (process dead): remove and acquire.
- If active: report "Another merge is in progress (<branch>). Waiting..." Retry every 10 seconds, max 5 minutes. If timeout: stop and tell the user.

### 2. Sync with parent

Invoke `mill-merge-in` via the Skill tool. This handles:
- No-op detection (already up to date)
- Checkpoint creation
- Merging parent into worktree
- Conflict resolution
- Verification
- Codeguide update

If mill-merge-in succeeds, capture the checkpoint branch name it reports (needed for rollback if steps 3–6 fail).

If mill-merge-in fails (reports rollback or unresolvable conflicts): release the merge lock (step 7) and report the failure to the user. Do not proceed.

### 3. Merge into parent

Determine the merge method:

Always direct squash merge. Mill never creates PRs — that is the user's responsibility via `/git-pr` or manually.

**Important:** Capture the child branch name before switching context — it is needed in Step 4:
```bash
CHILD_BRANCH=$(git branch --show-current)
```

```bash
# Switch to parent in the parent worktree or repo root
cd <parent-path>
git merge --squash <worktree-branch>
```
```bash
git commit -m "<task title>"
git push
```
Squash merge collapses all worktree commits into a single commit on the parent branch.

### 4. Update parent's child registry

If `<parent-path>/_millhouse/children/` exists, find the child registry file whose YAML frontmatter contains `branch: <CHILD_BRANCH>` (search all `.md` files in the folder). If found:
- Update `status: active` to `status: merged`
- Add `merged: <UTC ISO 8601 timestamp>` field to the frontmatter

If `_millhouse/children/` does not exist in the parent, skip silently (backward compatibility with pre-change worktrees). If no matching file is found, skip silently.

### 5. Notify

Run the **Notification Procedure** (same as mill-go — see below) with `COMPLETE: Merge successful for <branch>` (info-level — toast + status only, skip Slack).

### 6. Cleanup

After successful direct merge (already running in `<parent-path>` from step 3):

```bash
git worktree remove <worktree-path>
git branch -D <worktree-branch>
git branch -D mill-checkpoint-<name>
```

If `git worktree remove` fails (typically because VS Code locks the directory), fall back to unlinking without deleting the directory:

```bash
git worktree remove <worktree-path> --force
```

If that also fails, detach the worktree registration and prune:

```bash
git worktree prune
git branch -D <worktree-branch>
git branch -D mill-checkpoint-<name>
```

The orphaned directory can be deleted later (manually or by `mill-status`).

If the branch was pushed to remote:
```bash
git push origin --delete <worktree-branch>
```

### 7. Release merge lock

Delete `<parent-path>/_millhouse/scratch/merge.lock`.

This step runs in ALL exit paths — success, failure, or rollback. Use trap/finally pattern.

---

## Rollback

If any step fails after step 2 (sync with parent) has succeeded, use the checkpoint branch name captured from mill-merge-in's output in step 2:

```bash
git reset --hard mill-checkpoint-<name>
```

Then release the merge lock. Run the **Notification Procedure** with `BLOCKED: Merge failed for <branch> — rolled back to checkpoint`. Report the failure to the user. Do NOT delete the checkpoint branch on failure — preserve it for investigation.

---

## Notification Procedure

### Step 1: Update status file (always)

Write the event to `_millhouse/scratch/status.md`. For blocking events, ensure `blocked: true` and `blocked_reason:` are set. For completion events, ensure `phase: complete`. Status file updates are the calling skill's responsibility, not the script's.

### Step 2: Send notification

```bash
bash "$(git rev-parse --show-toplevel)/plugins/mill/scripts/notify.sh" \
  --event "<EVENT>" \
  --branch "$(git branch --show-current)" \
  --detail "<detail>" \
  --urgency "<info|high>"
```

Urgency per event:
- Merge successful -> `--urgency info` (toast + status only, skip Slack)
- Merge failed / rolled back -> `--urgency high` (all channels)

---

## Board Updates

- Merge complete -> no board update needed. The child worktree's `status.md` already has `phase: complete`.
