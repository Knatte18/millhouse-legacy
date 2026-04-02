# Merge Strategy

## Overview

`helm-merge` handles merging a completed worktree back to its parent branch. The strategy: merge parent INTO worktree first (resolve conflicts in the feature context), verify, audit, then merge worktree INTO parent (clean merge).

## Flow

### 1. Checkpoint

Before anything, create a checkpoint:

```bash
CHECKPOINT=$(git rev-parse HEAD)
git branch helm-checkpoint-<worktree-name>
```

If anything goes wrong, reset to checkpoint. This is non-negotiable.

### 2. Merge parent into worktree

```bash
git merge <parent-branch>
```

This catches up the worktree with any changes made on the parent since the worktree was created. Conflicts are resolved here — in the feature context where CC understands the code.

### 3. Verify

Run full verification (lint, type-check, build, test). The merged code must pass everything.

If verification fails: diagnose and fix. Max 3 attempts. If unresolvable, reset to checkpoint and escalate to user.

### 4. Merge worktree into parent

Two paths:

**Direct merge** (parent is not `main`, or worktree-to-worktree):
```bash
git checkout <parent-branch>
git merge <worktree-branch>
```

**PR** (parent is `main` and team review required):
```bash
gh pr create --title "<feature title>" --body "<generated description>"
```

PR description generated from:
- Knowledge files (`_helm/knowledge/`)
- Changelog entries
- Plan context
Human team member reviews the PR. Should be straightforward because CC already did code-review per task.

### 5. Knowledge propagation

Copy `_helm/knowledge/` from worktree to parent. Since `_helm/` is tracked, this happens automatically with the merge. If the parent is another worktree, its next `helm-go` task will read the accumulated knowledge.

### 6. Codeguide update

Run `codeguide-update` with scope `git diff helm-checkpoint-<worktree-name>..HEAD`. This captures all changes introduced by the worktree, including conflict resolutions. Must run BEFORE the final merge to parent (between steps 3 and 4), when the diff is still meaningful.

### 7. Cleanup

After successful merge (or PR approval + merge):

```bash
git worktree remove <path>
git branch -D <branch-name>
git push origin --delete <branch-name>
git branch -D helm-checkpoint-<worktree-name>
```

Never cleanup on failure. Preserve worktree for investigation.

### 8. Kanban update

Move the issue to **Done**. Post a merge summary comment.

## Merge Locking

Two sibling worktrees merging to the same parent simultaneously causes conflicts. Prevention:

1. **Resolve parent path:** Run `git worktree list --porcelain`, find the entry whose `branch` matches the parent branch name. Extract its `worktree` path. If parent is the repo root (no worktree entry), use the repo root path.
2. **Acquire lock:** Write `<parent-path>/_helm/scratch/merge.lock` with PID and timestamp. Create `_helm/scratch/` in the parent if it doesn't exist.
3. **If lock exists:** Read PID from lock file. Check if process is alive (`kill -0 <PID>`). If stale (process dead), remove and acquire. If active, wait and retry every 10 seconds (max 5 minutes timeout).
4. **Release lock** after merge completes (success or failure). Use a trap/finally pattern to ensure release even on crash.

## Conflict Resolution

When `git merge <parent-branch>` produces conflicts:

1. List conflicting files: `git diff --name-only --diff-filter=U`
2. For each file:
   - Whitespace/formatting only → accept worktree version
   - Package lock files (`package-lock.json`, `yarn.lock`) → accept worktree version, then regenerate by running the install command
   - Other generated files (build artifacts) → accept worktree version
   - Real code conflicts → attempt resolution based on understanding both sides
3. If conflicts remain unresolvable: reset to checkpoint, escalate to user with the list of conflicting files and context.

Never force-merge. Never `-X theirs` or `-X ours` on real code conflicts.

## Rollback

If any step fails after checkpoint:

```bash
git reset --hard helm-checkpoint-<worktree-name>
git branch -D helm-checkpoint-<worktree-name>
```

Worktree is back to pre-merge state. User can investigate and retry.
