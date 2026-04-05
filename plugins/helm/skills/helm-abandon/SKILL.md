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

Read `_git/config.yaml` if it exists; extract `parent-branch`. If not found, fall back to `parent:` in `_helm/scratch/status.md` (different field name — backwards compat with pre-migration worktrees). If neither exists, ask the user which branch to merge into. The resolved parent-branch must be in memory before Step 4 removes the worktree.

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

### 4. Capture task block from child board

Read the full task block (title heading + body) from the child worktree's `kanbans/board.kanban.md` **before** the worktree is deleted. This is the only copy of the task body — `_helm/scratch/status.md` has only the title, not the body. Store the captured block in memory for use in Step 8 (Kanban update).

### 5. Remove worktree

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

### 6. Delete branch

```bash
git branch -D <branch-name>
```

If the branch was pushed to remote:
```bash
git push origin --delete <branch-name>
```

### 7. Delete checkpoint branch

If a checkpoint branch exists (`helm-checkpoint-<name>`):
```bash
git branch -D helm-checkpoint-<name>
```

### 8. Kanban update

Use the task block (title + body) captured in Step 4.

The child's `board.kanban.md` is destroyed with the worktree — no explicit removal needed.

Add the task back to `## Backlog` column in the **parent's** `kanbans/backlog.kanban.md`. Locate parent worktree path via `git worktree list --porcelain` or `_helm/scratch/status.md` `parent:` field.

Since backlog is git-tracked, check for modifications before committing: `git -C <parent-path> status --porcelain kanbans/backlog.kanban.md` — if output is non-empty, report the conflict and stop. Otherwise commit from parent context:

```bash
git -C <parent-path> add kanbans/backlog.kanban.md
git -C <parent-path> commit -m "revert: return <task> to backlog (abandoned)"
git -C <parent-path> push
```

Validate backlog per `doc/modules/validation.md` (3-column rules: Backlog, Spawn, Delete).

### 9. Report

> "Worktree `<path>` abandoned. Branch `<branch>` deleted. Task moved to Backlog."

---

## Kanban Updates

- Abandon → child's `board.kanban.md` is destroyed with worktree. Task is added back to parent's `kanbans/backlog.kanban.md` `## Backlog` column (git-tracked — commit and push required).
