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

Verify this is a mill-managed worktree:
- Read the YAML code block in `_millhouse/task/status.md`. If the file does not exist, or does not contain both a `task:` and a `phase:` field in the YAML code block, stop: "This worktree is not managed by mill (no status.md with task/phase). Use `git worktree remove` to clean up manually-created worktrees."

Read `_millhouse/config.yaml` if it exists; extract `git.parent-branch`, `git.base-branch`, and `git.require-pr-to-base` (default `false` if missing). If `parent-branch` is not found, fall back to `parent:` from the YAML code block in `_millhouse/task/status.md`. If neither exists, ask the user which branch to merge into.

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

If mill-merge-in succeeds, capture the checkpoint branch name it reports (needed for rollback if steps 3–7 fail).

If mill-merge-in fails (reports rollback or unresolvable conflicts): release the merge lock (step 7) and report the failure to the user. Do not proceed.

### 4. Merge into parent

**Idempotency check.** Do NOT use `git branch --contains <child-branch> <parent-branch>` for squash-merge detection — that command checks commit ancestry, which `git merge --squash` does not preserve (the squash commit is new; the child's original commits are absent from the parent's history). Instead, run `git -C <parent-path> merge --squash <child-branch>` and detect idempotency from the output: if git reports "Already up to date" or if the subsequent `git commit` returns "nothing to commit", the squash was already applied in a prior run. When either signal is detected at the merge/commit step, skip the push and proceed directly to Step 4.5 (write `[done]`). This correctly handles the recovery scenario where the squash succeeded but the tasks.md write (Step 4.5) failed.

**Important:** Capture the child branch name before switching context — it is needed in Step 5:
```bash
CHILD_BRANCH=$(git branch --show-current)
```

Determine the merge method:

**If `require-pr-to-base` is `true` AND `parent-branch` equals `base-branch`:** create a pull request instead of squash-merging.

1. Verify `gh` is available and authenticated:
   ```bash
   gh --version
   gh auth status
   ```
   If either command fails, stop: "gh CLI is required for PR creation but is not available or not authenticated. Install gh and run `gh auth login`."

2. Push the branch if not already pushed:
   ```bash
   git push
   ```

3. Create the PR. Use the `task:` field from the YAML code block in `_millhouse/task/status.md` as the PR title:
   ```bash
   gh pr create --title "<task title>" --body "Merging branch \`$CHILD_BRANCH\` to \`<base-branch>\`."
   ```

4. Update the YAML code block in `_millhouse/task/status.md` with `phase: pr-pending` and add a `pr_url:` field containing the PR URL returned by `gh pr create`.

5. Update parent's child registry (same as Step 5 of the normal path): if `<parent-path>/_millhouse/children/` exists, find the child registry file for `$CHILD_BRANCH` and update `status: active` to `status: pr-pending`. Add a `pr_url:` field with the PR URL. Skip silently if the registry or file is not found.

6. Skip Step 6 (Notify). Jump to Step 7 (release merge lock). Report the PR URL to the user.

**Note:** The `[done]` helper write (Step 4.5) is SKIPPED on this path. tasks.md keeps the `[completed]` marker written by mill-go at Phase: Completion. A future enhancement may add PR-landed detection; for now, `[done]` is not written for PR-path merges.

If `gh pr create` fails, treat as a Step 4 failure: roll back to the checkpoint (same rollback procedure as below), release merge lock (Step 7), and report error.

**Otherwise (default):** direct squash merge. Use `git -C <parent-path>` for every git command so the shell cwd stays inside the child worktree (worktree isolation rule — see `conversation/SKILL.md`).

```bash
git -C <parent-path> merge --squash <worktree-branch>
git -C <parent-path> commit -m "<task title>"
git -C <parent-path> push
```
Squash merge collapses all worktree commits into a single commit on the parent branch.

### 4.5. Write `[done]` to tasks.md

**This step runs ONLY on the direct-merge path (not PR-path).** After Step 4's squash merge succeeds (or after the idempotency check identifies the merge as already done), call the helper to mark the task `[done]` on the tasks branch.

1. Load `_millhouse/config.yaml` via `millpy.core.config.load`.
2. Resolve tasks.md path via `millpy.tasks.tasks_md.resolve_path(cfg)`.
3. Parse with `tasks_md.parse`, find the task by title (from the `task:` field in `_millhouse/task/status.md`), replace its phase marker with `done` (overwriting `[active]`, `[completed]`, or a missing marker).
4. Call `millpy.tasks.tasks_md.write_commit_push(cfg, rendered, f"task: mark {task_title} [done]")`.

If `write_commit_push` raises (network failure, rebase conflict, lock contention): DO NOT roll back the merge (it's already committed on the parent). Report the error to the user with the message "Merge succeeded but tasks.md write failed: <err>. Re-run `mill-merge` to retry the tasks.md write — Step 4's idempotency check will skip the merge and proceed directly to this step." Release the merge lock (Step 7) and exit with error.

### 5. Update parent's child registry

If `<parent-path>/_millhouse/children/` exists, find the child registry file whose YAML frontmatter contains `branch: <CHILD_BRANCH>` (search all `.md` files in the folder). If found:
- Update `status: active` to `status: merged`
- Add `merged: <UTC ISO 8601 timestamp>` field to the frontmatter

If `_millhouse/children/` does not exist in the parent, skip silently (backward compatibility with pre-change worktrees). If no matching file is found, skip silently.

### 6. Notify

Run the **Notification Procedure** (same as mill-go — see below) with `COMPLETE: Merge successful for <branch>` (info-level — toast + status only, skip Slack).

### 7. Release merge lock

Delete `<parent-path>/_millhouse/scratch/merge.lock`.

This step runs in ALL exit paths — success, failure, or rollback. Use trap/finally pattern.

### 8. Report

> "Merge complete. Run mill-cleanup from the parent worktree to remove the merged worktree and branch."

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

Write the event to the YAML code block in `_millhouse/task/status.md`. For blocking events, ensure `blocked: true` and `blocked_reason:` are set. For completion events, ensure `phase: complete`. Status file updates are the calling skill's responsibility, not the script's.

### Step 2: Send notification

```bash
PYTHONPATH=<SCRIPTS_DIR> python -m millpy.entrypoints.notify \
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

- Merge complete (direct-merge path) -> task marked `[done]` on the tasks branch via `millpy.tasks.tasks_md.write_commit_push`. PR path leaves tasks.md at `[completed]` (from mill-go) — no `[done]` write until a future enhancement adds PR-landed detection.
- Worktree, branch, and children registry removal are deferred to `mill-cleanup`, which runs from the parent worktree in a separate invocation.
