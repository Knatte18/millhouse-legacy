---
name: mill-inspect
description: Toggle inspect mode to view mill-go changes as uncommitted diffs in VS Code.
---

# mill-inspect

Toggle between normal mode and inspect mode. In inspect mode, all commits made since the branch point are temporarily "uncommitted" so they appear as unstaged modifications in VS Code Source Control — making it easy to review what mill-go did. Run again to restore all commits.

---

## Entry

Read `_millhouse/config.yaml`. If it does not exist, stop and tell the user to run `mill-setup` first.

**Worktree guard:** Must be in a child worktree, not the main worktree. Detect using `git worktree list --porcelain` — if the current path is the first/main entry, stop: "mill-inspect must be run from a child worktree, not the main repo."

---

## Toggle Detection

Check whether `mill-inspect-save` tag exists:

```bash
git tag -l mill-inspect-save
```

- Tag **absent** -> enter Inspect mode (uncommit)
- Tag **present** -> enter Uninspect mode (recommit)

---

## Inspect Mode (tag absent)

### 1. Check for uncommitted changes

```bash
git status --porcelain
```

If output is non-empty: warn the user that uncommitted changes exist and will intermingle with the inspected diff, making review confusing. Recommend committing or stashing first. Ask for confirmation before proceeding.

### 2. Resolve parent branch

Read `git.parent-branch` from `_millhouse/config.yaml`. If not found, fall back to `git.base-branch`. If neither exists, default to `main`.

### 3. Compute merge-base

```bash
git merge-base HEAD <parent-branch>
```

If this fails (e.g., no common ancestor), stop and report the error.

### 4. Save current HEAD

```bash
git tag mill-inspect-save
```

### 5. Uncommit

```bash
git reset --mixed <merge-base>
```

HEAD moves to the branch point. Files on disk stay unchanged. All changes since the branch point now appear as unstaged modifications in VS Code Source Control.

### 6. Report

```
Inspect mode active.
All changes since branch point are now visible as unstaged modifications in VS Code Source Control.

Do NOT commit while in inspect mode — new commits will be lost on uninspect.

Run /mill-inspect again to restore commits.
```

---

## Uninspect Mode (tag present)

### 1. Restore commits

```bash
git reset --mixed mill-inspect-save
```

HEAD moves back to the saved commit. All original commits are restored — messages, order, everything intact. Files on disk are unchanged.

### 2. Delete tag

```bash
git tag -d mill-inspect-save
```

### 3. Report

```
Commits restored. Inspect mode deactivated.
```
