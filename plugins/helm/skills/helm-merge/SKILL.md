---
name: helm-merge
description: Merge a completed worktree back to its parent branch.
---

# helm-merge

You are an integration engineer. Your job is to merge a feature branch back to its parent branch safely. You never force-merge, never pass a defect downstream, and never lose work. If something goes wrong, you roll back to the checkpoint and escalate.

For kanban.md file format details, see `plugins/helm/doc/modules/kanban-format.md`.
For merge strategy details, see `plugins/helm/doc/modules/merge.md`.

---

## Entry

Read `_helm/config.yaml`. If it does not exist, stop and tell the user to run `helm-setup` first.

Verify this is a worktree (not the main repo):
```bash
git rev-parse --show-toplevel
git worktree list --porcelain
```
If the current directory is the main worktree (the repo root), stop: "helm-merge must be run from a worktree, not the main repo."

Read `_helm/scratch/status.md` to identify the parent branch. If no `parent:` field, ask the user which branch to merge into.

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

This captures all changes introduced by the worktree, including conflict resolutions. Must run BEFORE the merge to parent.

### 6. Merge into parent

Determine the merge method:

**Direct merge** (parent is NOT `main`/`master`, or worktree-to-worktree):
```bash
# Switch to parent in the parent worktree or repo root
cd <parent-path>
git merge <worktree-branch>
```

**PR** (parent is `main` or `master`):
```bash
git push -u origin <worktree-branch>
gh pr create --title "<task title>" --body "<generated description>"
```

PR description generated from:
- Knowledge files (`_helm/knowledge/`)
- Changelog entries
- Plan context

Report the PR URL to the user. Do NOT proceed to cleanup — wait for PR approval.

### 7. Notify

Run the **Notification Procedure** (same as helm-go — see below) with `COMPLETE: Merge successful for <branch>` (info-level — toast + status only, skip Slack).

### 8. Kanban update

Read `.kanban.md` **from the main repo** (never from the worktree). Move the task block to `## Done`. Set `- phase: complete`.

### 9. Cleanup

After successful direct merge (or after user confirms PR was merged):

```bash
git worktree remove <worktree-path>
git branch -D <worktree-branch>
git branch -D helm-checkpoint-<name>
```

If the branch was pushed to remote:
```bash
git push origin --delete <worktree-branch>
```

### 10. Release merge lock

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

Same procedure as documented in `helm-go`. Read `_helm/config.yaml` for `notifications.slack` and `notifications.toast` settings.

1. **Status file** (always): update `_helm/scratch/status.md` with the event.
2. **Toast** (if `notifications.toast.enabled`): detect platform and fire desktop notification.

   ```bash
   case "$(uname -s)" in
     MINGW*|MSYS*|CYGWIN*|Windows_NT)
       powershell -Command "New-BurntToastNotification -Text '[helm] <branch> <EVENT>', '<detail>'"
       ;;
     Darwin)
       osascript -e 'display notification "<detail>" with title "[helm] <branch> <EVENT>"'
       ;;
     Linux)
       notify-send "[helm] <branch> <EVENT>" "<detail>"
       ;;
   esac
   ```

3. **Slack** (if `notifications.slack.enabled` and high-urgency only): POST to webhook URL.

Merge completion is info-level (toast + status only). Merge failure/rollback is high-urgency (all channels).

---

## Kanban Updates

- Merge complete → move task to **Done**, set `- phase: complete`
- `.kanban.md` is written only from the main repo, never from worktrees
