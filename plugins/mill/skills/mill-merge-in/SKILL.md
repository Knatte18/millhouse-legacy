---
name: mill-merge-in
description: Merge parent branch into the current branch. Standalone sync operation.
---

# mill-merge-in

Merge the parent branch into the current branch. This is a standalone operation for syncing with upstream changes. It does not acquire the merge lock (only modifies the current branch). mill-merge calls this internally as its first step.

---

## Entry

Read `.millhouse/config.yaml`. If it does not exist, stop and tell the user to run `mill-setup` first.

Extract `git.parent-branch` as the default merge source. If not found, fall back to `parent:` in `.millhouse/task/status.md`. If neither exists, ask the user which branch to merge from.

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `<branch>` | parent branch from config | Branch to merge from |

If a branch argument is provided, use it instead of the config default.

---

## Steps

### 1. Check for new commits

```bash
git log HEAD..<parent-branch> --oneline
```

If no output (no new commits on parent since this branch diverged): report "Nothing to merge — already up to date." and exit immediately. No checkpoint, no verify, no codeguide-update.

### 2. Create checkpoint

```bash
git branch mill-checkpoint-$(git rev-parse --abbrev-ref HEAD | tr '/' '-')
```

Record the checkpoint branch name. If anything goes wrong after this point, roll back to the checkpoint.

### 3. Merge parent into current branch

```bash
git merge <parent-branch>
```

**If conflicts occur:**
1. List conflicting files: `git diff --name-only --diff-filter=U`
2. For each file:
   - Whitespace/formatting only -> accept current branch version
   - Package lock files (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`) -> accept current branch version, then regenerate with the install command
   - Other generated files (build artifacts) -> accept current branch version
   - Real code conflicts -> attempt resolution based on understanding both sides
3. If conflicts are unresolvable: roll back to checkpoint, escalate to user with the list of conflicting files.

Never use `-X theirs` or `-X ours` on real code conflicts.

### 4. Verify

Run full verification (the `verify` command from plan frontmatter if available in `.millhouse/task/plan.md`, or the project's standard build/test command).

If verify is `N/A` (no test suite): skip verification.

If verification fails:
- Diagnose and fix. Max 3 attempts.
- If unresolvable after 3 attempts: roll back to checkpoint, escalate to user.

### 5. Codeguide update

If `_codeguide/Overview.md` exists, invoke `codeguide-update` scoped to the checkpoint diff:

```bash
git diff mill-checkpoint-<name>..HEAD
```

This captures all changes introduced by the merge, including conflict resolutions.

### 6. Report

```
Merged <parent-branch> into <current-branch>. <N> commits integrated.
```

---

## Rollback

If any step fails after checkpoint creation:

```bash
git reset --hard mill-checkpoint-<name>
```

Do NOT delete the checkpoint branch on failure — preserve it for investigation. Report the failure to the caller (or user if run standalone).

---

## No-op Guarantee

When there are no new commits to merge (step 1 produces no output), mill-merge-in exits immediately with no side effects: no checkpoint branch created, no verification run, no codeguide update. This ensures mill-merge can call it as a fast first step.
