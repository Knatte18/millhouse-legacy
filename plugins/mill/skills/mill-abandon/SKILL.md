---
name: mill-abandon
description: Discard a worktree and unmark the task in tasks.md.
---

# mill-abandon

Discard a worktree and all its work. Removes the phase marker from the task in `tasks.md`, making it available again. This is a destructive operation — always require explicit user confirmation.

---

## Entry

Read `_millhouse/config.yaml`. If it does not exist, stop and tell the user to run `mill-setup` first.

Verify this is a worktree (not the main repo):
```bash
git rev-parse --show-toplevel
git worktree list --porcelain
```
If the current directory is the main worktree, stop: "mill-abandon must be run from a worktree, not the main repo."

Read the current branch name:
```bash
git branch --show-current
```

Read `_millhouse/scratch/status.md` if it exists to identify the task title.

Read `_millhouse/config.yaml` if it exists; extract `git.parent-branch`. If not found, fall back to `parent:` in `_millhouse/scratch/status.md`. If neither exists, ask the user which branch to merge into.

Resolve the parent worktree path: run `git worktree list --porcelain` and find the entry whose `branch` field matches the parent branch name. Extract its `worktree` path and store it. This path is used in Steps 5, 6, and 9. The resolved parent-branch and parent-path must be in memory before Step 4 removes the worktree.

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

### 4. Capture task info from status.md

Read `task:` and `task_description:` from the child worktree's `_millhouse/scratch/status.md` **before** the worktree is deleted. Store the task title in memory for use in Step 9 (tasks.md update).

### 5. Update parent's child registry

Resolve the parent worktree path (already resolved at Entry via `git.parent-branch`). If `<parent-path>/_millhouse/children/` exists, find the child registry file whose YAML frontmatter contains `branch: <BRANCH_NAME>` (the branch name captured at Entry). If found:
- Update `status: active` to `status: abandoned`
- Add `abandoned: <UTC ISO 8601 timestamp>` field to the frontmatter

If `_millhouse/children/` does not exist in the parent, skip silently (backward compatibility). If no matching file is found, skip silently.

### 6. Remove worktree

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

### 7. Delete branch

```bash
git branch -D <branch-name>
```

If the branch was pushed to remote:
```bash
git push origin --delete <branch-name>
```

### 8. Delete checkpoint branch

If a checkpoint branch exists (`mill-checkpoint-<name>`):
```bash
git branch -D mill-checkpoint-<name>
```

### 9. Update tasks.md

Resolve the parent worktree path (already resolved at Entry). Read `<parent-path>/tasks.md`. Find the task's `## ` heading (match by task title captured in Step 4). Remove the `[phase]` marker from the heading, making the task unclaimed again. E.g., `## [implementing] Fix login` becomes `## Fix login`.

Stage, commit, and push from the parent worktree:
```bash
cd <parent-path>
git add tasks.md
git commit -m "task: abandon <task-title>"
git push
```

### 10. Report

> "Worktree `<path>` abandoned. Branch `<branch>` deleted. Task unmarked in tasks.md."

---

## Board Updates

- Abandon -> task's `[phase]` marker is removed from `tasks.md` (commit + push from parent worktree).
