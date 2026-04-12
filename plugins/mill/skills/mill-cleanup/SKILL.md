---
name: mill-cleanup
description: Clean up merged, abandoned, and stale worktrees, branches, and task entries.
---

# mill-cleanup

Single source of truth for removing merged, abandoned, and stale git state. `mill-merge` and `mill-abandon` only update status flags and registry entries — they never touch git state. `mill-cleanup` is run separately from the parent worktree after the user has closed terminals and VS Code in any child worktrees.

Cleanup operates without per-item confirmation: categories it handles (merged, abandoned, done, orphans, stale checkpoints) are clearly-flagged. If it encounters a worktree it cannot remove (locked, uncommitted work), it skips with a warning.

---

## Entry

Verify this is the main worktree (not a child):
```bash
git rev-parse --show-toplevel
git worktree list --porcelain
```
If the current directory is NOT the main worktree (first entry in `git worktree list`), stop: "mill-cleanup must be run from the main worktree, not a child."

Read `_millhouse/config.yaml`. If it does not exist, stop and tell the user to run `mill-setup` first.

Resolve repo root via `git rev-parse --show-toplevel`.

---

## Junction safety

**Hard constraint:** Any code that removes a path under `_millhouse/children/<slug>/` (the junction location) OR any path that might be a reparse point MUST use `(Get-Item $path).Delete()` or `cmd /c "rmdir "$path""`. NEVER use `Remove-Item -Recurse -Force` on a reparse-point path.

**Why:** `Remove-Item -Recurse -Force` on a junction follows the reparse point and deletes the contents of the TARGET directory — for `_millhouse/children/<slug>/` (junction → child's `_millhouse/task/`), this would wipe out the child's live task state. Catastrophic data loss.

**Detection pattern:**
```powershell
$item = Get-Item $path -ErrorAction SilentlyContinue
if ($item -and $item.Attributes.ToString().Contains("ReparsePoint")) {
    $item.Delete()  # Safe: deletes only the reparse point
} else {
    Remove-Item $path -Recurse -Force  # Only for real directories
}
```

---

## Steps

mill-cleanup runs in three phases: **Phase 0: Legacy-scratch sweep** (one-time migration cleanup), **Phase 1: Detection** (read-only scan that builds a cleanup set), and **Phase 2: Execution** (performs the actions). No user confirmation between phases — the skill just runs.

### Phase 0: Legacy-scratch sweep

Runs once, is idempotent, and cleans up migration-era hardlinks/junctions before any detection scan runs. This phase handles the transition period where `_millhouse/scratch/` held hardlinks to files that now live canonically in `_millhouse/task/`.

1. **Reviews-directory sweep (current worktree only):** if `_millhouse/task/reviews/` exists AND its `LinkType` is `Junction` AND `_millhouse/scratch/reviews/` exists as a regular directory:
   a. Delete the junction: `(Get-Item _millhouse/task/reviews).Delete()`. This removes only the reparse point — `_millhouse/scratch/reviews/` and its contents are unaffected.
   b. Remove `_millhouse/scratch/reviews/` and its contents: `Remove-Item -Recurse -Force _millhouse/scratch/reviews`. Safe — it is a regular directory, not a reparse point.
   c. Recreate `_millhouse/task/reviews/` as a real empty directory: `New-Item -ItemType Directory -Path _millhouse/task/reviews -Force | Out-Null`.

2. **File-hardlink sweep (current worktree only):** for each file in `{ status.md, plan.md, discussion.md, implementer-brief-instance.md }`: if `_millhouse/scratch/<file>` exists AND its `LinkType` is `HardLink` AND `_millhouse/task/<file>` also exists: run `Remove-Item _millhouse/scratch/<file>`. `Remove-Item` on a hardlink decrements the inode's link count without deleting the underlying data; the file survives at `_millhouse/task/<file>`.

3. After the sweep, `_millhouse/scratch/` should contain only genuinely ephemeral files.

4. This sweep is idempotent: re-running it after migration-era state is already cleaned is a no-op.

### Phase 1: Detection

Build a cleanup set by scanning the following sources in order. Collect each candidate with its category, branch (if any), worktree path (if any), task title (if any), and any captured context (e.g., abandon protocol). Deduplicate by branch name and task title — a task found in multiple scans is processed once.

#### Scan 1: Children registry
Scan `_millhouse/children/*.md`. For each `.md` file, parse the YAML frontmatter. Collect entries where `status:` is one of `merged`, `abandoned`, or `complete`. For each, capture `branch`, `task`, the file path.

For `abandoned` entries: try to read the child's `_millhouse/task/status.md` (resolved via `git worktree list --porcelain` to find the worktree path for that branch, or via the `_millhouse/children/<slug>/` junction if present). Extract the `## Abandon` section if present. Capture `reason`, `last_phase`, `last_step`, `context`. Store these for the execution phase — do not re-read during execution.

Skip entries with `status: active` or `status: pr-pending`.

#### Scan 2: Worktrees with phase complete
Run `git worktree list --porcelain`. For each worktree other than the main one: read its `_millhouse/task/status.md`. If the YAML code block has `phase: complete` AND no matching child registry entry was found in Scan 1 (no entry for this branch), add to the cleanup set as a "complete" candidate.

#### Scan 3: tasks.md markers
Read `tasks.md` in the project root. Collect all `## [done] <Title>` and `## [abandoned] <Title>` headings.

For each `[done]` heading: add to the cleanup set as a "done task" with title. Match against Scan 1 entries by title — if both exist, treat as one entry (dedup).

For each `[abandoned]` heading: match against Scan 1 by title. If matched, use the captured context from Scan 1. If no matching child registry and no live worktree exists for this title, add as a straggler with no context: it will be unmarked to unclaimed without a protocol block.

The `[abandoned]` marker is introduced to tasks.md by `mill-abandon` (see the mill-abandon skill). Its presence here is expected after abandon has run.

#### Scan 4: Orphan directories
Derive the worktree container path: `<parent-of-repo-root>/<reponame>.worktrees/` where `<parent-of-repo-root>` is the parent directory of `git rev-parse --show-toplevel` and `<reponame>` is the basename of the repo root.

**Hub-layout skip:** if a `.bare` directory exists at `<parent-of-repo-root>/.bare`, this is a hub-layout repo. In hub layout, orphan directories live directly under the hub root (not under `.worktrees`). Scan the hub root itself (not the container) for subdirectories not listed in `git worktree list` output and not `.bare`. Add each as an orphan.

**Non-hub layout:** scan `<parent-of-repo-root>/<reponame>.worktrees/` for subdirectories not listed in `git worktree list` output. Add each as an orphan.

If the container directory does not exist, skip this scan (nothing to clean).

#### Scan 5: Stale checkpoint branches
Run `git branch --list 'mill-checkpoint-*'`. Checkpoint branch names follow the pattern `mill-checkpoint-<branch-name>` where forward slashes in the branch name are replaced with hyphens.

For each checkpoint branch: determine the underlying branch by stripping the `mill-checkpoint-` prefix and (best-effort) reversing the hyphen-to-slash mapping. If the underlying branch no longer exists (check via `git branch --list`) AND no live worktree references it, mark the checkpoint for deletion.

#### Scan 6: Empty container directory
If Scan 4 identified orphans in `<parent-of-repo-root>/<reponame>.worktrees/`, the container itself may become empty after removals. Do not mark the container for removal during detection — instead, re-check after execution (see Execution step below).

#### Scan 7: Remote branches for merged children
For each entry from Scan 1 with `status: merged`: check if the remote still has the branch (`git ls-remote origin <branch>`). If so, mark for remote deletion.

#### Scan 8: Dangling junctions in _millhouse/children/
Enumerate `_millhouse/children/*` directory entries. For each entry that is a reparse point (junction): attempt to read `<junction>/status.md`. If the read throws an exception (target missing — the child worktree was removed externally), add this junction to a "dangling junctions" list for removal in the execution phase.

### Phase 2: Execution

Process the cleanup set in the following order. For each action that fails non-trivially (git-lock, uncommitted changes, OS-level file locks), skip with a warning and continue — do not abort the entire cleanup.

#### Action 1: Remove worktrees
For each live worktree in the cleanup set (from Scans 1, 2, and any matched by Scan 3):
- **First**, verify the worktree has no uncommitted changes: `git -C <path> status --porcelain`. If output is non-empty, skip with warning: "worktree <path> has uncommitted changes; commit or stash before cleanup." Do not attempt removal.
- Try `git worktree remove <path>` without force first.
- If it fails because of a git lock file (`.git/worktrees/<name>/locked`), skip with warning: "worktree <path> is git-locked; unlock manually and re-run cleanup." Do not retry with force.
- If it fails for other reasons (directory not empty, stale metadata), retry with `git worktree remove --force <path>`.
- If `--force` also fails (OS-level file locks: VS Code, terminal, editor holds a handle), skip with warning: "worktree <path> is in use; close terminals and VS Code and re-run cleanup."

#### Action 2: Delete local branches
For each branch marked for deletion (from Scans 1, 2):
- `git branch -D <branch>` — ignore errors if the branch is already gone.

#### Action 3: Delete remote branches
For each branch from Scan 7 (merged + still on remote):
- `git push origin --delete <branch>` — ignore errors if the remote is already gone.

#### Action 4: Delete checkpoint branches
For each stale checkpoint from Scan 5:
- `git branch -D mill-checkpoint-<name>` — ignore errors.

#### Action 5: Delete orphan directories
For each orphan directory from Scan 4:
- Remove the directory recursively (`rmdir`/`Remove-Item -Recurse`).
- If the directory contains files that are in use (rare for orphans), skip with warning.

#### Action 6: Remove empty container directory
If the `<parent-of-repo-root>/<reponame>.worktrees/` container still exists and is now empty (after Actions 1 and 5 ran), `rmdir` it. Skip silently if it still has contents (something was not cleaned up by earlier actions).

#### Action 7: Delete children registry entries and junctions
For each entry processed from Scan 1: delete its `.md` file from `_millhouse/children/`. Then remove the corresponding slug-named junction:
1. Derive the slug from the registry file's stem (strip the leading `<timestamp>-` prefix) or from the `branch:` frontmatter field (use the final path segment after any `/`).
2. Compute `$junctionPath = Join-Path $childrenDir $slug`.
3. Check for the junction using the detection pattern:
   ```powershell
   $junctionItem = Get-Item $junctionPath -ErrorAction SilentlyContinue
   if ($junctionItem -and $junctionItem.Attributes.ToString().Contains("ReparsePoint")) {
       $junctionItem.Delete()
       Write-Host "Removed junction: $junctionPath"
   }
   ```
   NEVER use `Remove-Item -Recurse -Force` on the junction path — see the Junction safety section above.
4. If no junction exists at `$junctionPath`, skip silently (backward compatibility with pre-junction worktrees).

Do this after the corresponding worktree/branch actions so the registry reflects the latest state during the run.

#### Action 7b: Remove dangling junctions
For each dangling junction identified in Scan 8: remove it via `(Get-Item $path).Delete()` and log the removal. This reaps junctions whose child worktree was deleted outside mill-cleanup.

#### Action 8: Update tasks.md
For each `[done]` task in the cleanup set: remove the entire block (the `## [done] <Title>` heading and all body lines until the next `## ` heading or EOF).

For each `[abandoned]` task in the cleanup set: replace the `## [abandoned] <Title>` heading with `## <Title>` (unmark to unclaimed). If an abandon protocol was captured in Scan 1, append a blockquote to the task body with this exact format:

```markdown
> **Previously abandoned (<YYYY-MM-DD>):** <reason>
> **Last phase:** <last_phase> (step <last_step>)
> **Context:** <context>
```

If a previous `> **Previously abandoned...` blockquote already exists anywhere in the task body, remove it before appending the new one (latest-only, no history accumulation). If no context was captured (straggler case, see Scan 3), do not append a blockquote — just unmark the heading.

#### Action 9: git worktree prune
Run `git worktree prune` to clean up any stale worktree metadata in `.git/worktrees/` left behind by orphan removal.

#### Action 10: Commit tasks.md changes
If `tasks.md` was modified in Action 8:
- `git add tasks.md`
- `git commit -m "task: cleanup <N> task(s)"` where `<N>` is the count of tasks processed (done + abandoned).
- `git push`

If no tasks were modified, skip.

### Phase 3: Report

Print a final summary:

```
Cleanup complete.
  Worktrees removed:      N
  Branches deleted:       N local, N remote
  Checkpoint branches:    N
  Orphan directories:     N
  Registry entries:       N
  tasks.md [done] blocks: N removed
  tasks.md [abandoned]:   N unmarked (M with protocol)

Skipped (with warnings):
  - <item>: <reason>
  - ...
```

If nothing was found to clean up, print: "No cleanup needed. Repository is in a clean state."

---

## Board Updates

- Merged child → `mill-merge` marks registry entry `merged`; `mill-cleanup` removes worktree, branch, registry entry. `[done]` task block removed from tasks.md and committed.
- Abandoned child → `mill-abandon` marks registry entry `abandoned`, writes protocol to child's `status.md`, marks tasks.md heading `[abandoned]`; `mill-cleanup` removes worktree, branch, registry entry, unmarks tasks.md heading (preserving protocol as blockquote).
- PR-pending child → both `mill-merge` and `mill-cleanup` leave it alone until the PR is merged externally, then normal merged-child cleanup applies on next run.
- Orphan directory or stale checkpoint → `mill-cleanup` removes it with no coordination (no registry entry exists).
