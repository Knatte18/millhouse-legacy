---
name: helm-abandon
description: Discard a worktree and move the task back to Backlog.
---

# helm-abandon

Discard a worktree and all its work. Moves the associated task back to Backlog. This is a destructive operation — always require explicit user confirmation.

For kanban.md file format details, see `plugins/helm/doc/modules/kanban-format.md`.

---

## Entry

Read `_helm/config.yaml`. If it does not exist, stop and tell the user to run `helm-setup` first.

Verify this is a worktree (not the main repo):
```bash
git rev-parse --show-toplevel
git worktree list --porcelain
```
If the current directory is the main worktree, stop: "helm-abandon must be run from a worktree, not the main repo."

Read the current branch name:
```bash
git branch --show-current
```

Read `_helm/scratch/status.md` if it exists to identify the task title.

---

## Steps

### 1. Check for uncommitted work

```bash
git status --porcelain
```

If there are uncommitted changes (staged or unstaged), warn the user:
> "This worktree has uncommitted changes. Abandon anyway?"

List the changed files so the user can see what will be lost.

### 2. Check for unmerged commits

```bash
git log <parent-branch>..HEAD --oneline
```

If there are commits that haven't been merged to the parent, warn the user:
> "This worktree has N commit(s) not merged to `<parent-branch>`. These will be permanently deleted."

Show the commit list.

### 3. Require confirmation

Present all warnings together, then ask:
> "Type 'abandon' to confirm, or anything else to cancel."

Never auto-abandon. Never skip confirmation, even if there are no warnings.

### 4. Remove worktree

The worktree must be removed from the parent repo context, not from within the worktree itself.

```bash
# Get paths before leaving
WORKTREE_PATH=$(git rev-parse --show-toplevel)
BRANCH_NAME=$(git branch --show-current)

# Navigate to parent repo (resolve from git worktree list)
cd <parent-repo-path>

# Remove the worktree
git worktree remove "$WORKTREE_PATH" --force
```

If remove fails (e.g., locked), report the error and stop. Do not force-delete the directory.

### 5. Delete branch

```bash
git branch -D <branch-name>
```

If the branch was pushed to remote:
```bash
git push origin --delete <branch-name>
```

### 6. Delete checkpoint branch

If a checkpoint branch exists (`helm-checkpoint-<name>`):
```bash
git branch -D helm-checkpoint-<name>
```

### 7. Kanban update

Search for the task in the parent worktree's kanban files (using the parent branch and task title from Entry, already read from status.md before worktree removal; find the parent's path via `git worktree list --porcelain`). Search in order: `kanbans/processing.kanban.md` → `kanbans/blocked.kanban.md` → `kanbans/done.kanban.md` → `kanbans/backlog.kanban.md`. Stop at first match. If the task is not found in any file, stop and report the error to the user.

- Cut the task block from the source file and paste it into `kanbans/backlog.kanban.md`.
- Update `[phase]` in the task's `###` heading to `[backlog]` (or remove the `[...]` suffix entirely).
- Validate all modified board files per `doc/modules/validation.md`. If validation fails, report the issue to the user and stop.
- Stage `kanbans/` and include it in the cleanup commit together with any other changes (branch deletion, checkpoint removal, etc.). Never commit kanban files alone.

### 8. Report

> "Worktree `<path>` abandoned. Branch `<branch>` deleted. Task moved to Backlog."

---

## Kanban Updates

- Abandon → search parent's `kanbans/` files for the task, move to `kanbans/backlog.kanban.md`, update `[backlog]` in heading
