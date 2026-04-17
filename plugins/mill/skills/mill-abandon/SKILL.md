---
name: mill-abandon
description: Mark a worktree task as abandoned. Captures abandon protocol and updates task status; git cleanup is deferred to mill-cleanup.
---

# mill-abandon

Mark a worktree's task as abandoned and capture a short protocol explaining why. Updates `status.md`, the parent's child registry, and the parent's `tasks.md` marker (via a merge-lock). **Does not remove the worktree, branch, or any git state** — those are handled by `mill-cleanup` after the user has closed terminals and VS Code in this worktree.

The rationale: deleting a worktree while VS Code or a terminal still holds file handles causes lock errors and orphaned processes. Splitting the work into two commands — mark-abandoned now, cleanup later from the parent — avoids this entirely.

---

## Entry

Read `_millhouse/config.yaml`. If it does not exist, stop and tell the user to run `mill-setup` first.

Verify this is a worktree (not the main repo):
```bash
git rev-parse --show-toplevel
git worktree list --porcelain
```
If the current directory is the main worktree, stop: "mill-abandon must be run from a worktree, not the main repo."

Verify this is a mill-managed worktree:
- Read the YAML code block in `_millhouse/task/status.md`. If the file does not exist, or does not contain both a `task:` and a `phase:` field in the YAML code block, stop: "This worktree is not managed by mill (no status.md with task/phase). Use `git worktree remove` to clean up manually-created worktrees."

Read the current branch name:
```bash
git branch --show-current
```

Read the YAML code block in `_millhouse/task/status.md` to identify the task title, current phase, and (if present) `current_step_name`.

Read `_millhouse/config.yaml`; extract `git.parent-branch`. If not found, fall back to `parent:` from the YAML code block in `_millhouse/task/status.md`. If neither exists, ask the user which branch is the parent.

Resolve the parent worktree path: run `git worktree list --porcelain` and find the entry whose `branch` field matches the parent branch name. Extract its `worktree` path and store it. This path is used in Steps 5 and 7.

---

## Steps

### 1. Check for uncommitted work

```bash
git status --porcelain
```

If there are uncommitted changes (staged or unstaged), warn the user:
> "This worktree has uncommitted changes. Abandon anyway? (They will be preserved until you run mill-cleanup, but the task will be marked abandoned.)"

List the changed files so the user can see what will be preserved.

### 2. Check for unmerged commits

```bash
git log <parent-branch>..HEAD --oneline
```

If there are commits that haven't been merged to the parent, warn the user:
> "This worktree has N commit(s) not merged to `<parent-branch>`. These will be preserved on the worktree's branch until mill-cleanup deletes the branch."

Show the commit list.

### 3. Require confirmation

Present all warnings together, then ask:
> "Type 'abandon' to confirm, or anything else to cancel."

Never auto-abandon. Never skip confirmation, even if there are no warnings.

### 4. Capture task info from status.md

Read `task:` and `task_description:` from the YAML code block in the child worktree's `_millhouse/task/status.md`. Store the task title for Step 7.

### 5. Update parent's child registry

If `<parent-path>/_millhouse/children/` exists, find the child registry file whose YAML frontmatter contains `branch: <BRANCH_NAME>` (the branch name captured at Entry). If found:
- Update `status: active` (or whatever current status) to `status: abandoned`
- Add `abandoned: <UTC ISO 8601 timestamp>` field to the frontmatter

If `_millhouse/children/` does not exist in the parent, skip silently (backward compatibility). If no matching file is found, skip silently.

### 6. Capture abandon reason and write protocol

**Capture the reason:**
- If the user invoked `mill-abandon "<reason>"` with a positional argument, use that string as the reason (single line, trimmed).
- Otherwise, prompt: "Why are you abandoning this task? (one line)" and read a single line from stdin.

**Auto-generate the context summary (2-3 lines):**
- Read the last 3 timeline entries from the `## Timeline` section of `_millhouse/task/status.md`.
- Read the task description (`task_description:`) from the YAML code block.
- Compose a 2-3 line summary: what the task was, what phase it reached, and (if applicable) what was the last completed step. Example: "Task: design cleanup skill. Reached implementing phase. Completed step 2 of 6 (mill-cleanup skill created); stopped before mill-abandon rewrite."

**Write the `## Abandon` section to the child's `_millhouse/task/status.md`:**

Read `plugins/mill/templates/status-abandoned.md`, strip the leading HTML comment, and substitute:
- `<ABANDON_REASON>` — user-provided reason.
- `<LAST_PHASE>` — `phase` field from the status.md YAML block.
- `<LAST_STEP>` — `current_step` field from the YAML block, or `N/A` if unset.
- `<CONTEXT_SUMMARY>` — the 2–3 line auto-generated summary.

Use the Edit tool to insert the substituted section after the closing ``` of the YAML code block and before the `## Timeline` section. If a `## Abandon` section already exists from a prior abandon, overwrite it (latest-only).

**Update the phase in the YAML code block** of `_millhouse/task/status.md` from its current value to `abandoned`. Insert a timeline entry `abandoned  <UTC ISO 8601 timestamp>` before the closing ``` of the `## Timeline` text block using the Edit tool.

### 7. Update parent's tasks.md (with merge-lock)

**Acquire merge-lock on the parent** — same pattern as mill-merge Step 1:

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
- If active: report "Another merge/abandon is in progress (<branch>). Waiting..." Retry every 10 seconds, max 5 minutes. If timeout: stop and tell the user.

**Perform the tasks.md update** (under the lock):

Resolve the parent's project root by computing the project subdirectory offset (working directory minus git root) and applying it to the parent worktree path. Read `<parent-project-root>/tasks.md`. Find the task's `## ` heading (match by task title captured in Step 4). Replace the `[phase]` marker with `[abandoned]`. E.g., `## [active] Fix login` becomes `## [abandoned] Fix login`.

Stage, commit, and push from the parent worktree **without changing cwd** (worktree isolation rule — see `conversation/SKILL.md`):
```bash
git -C <parent-path> add tasks.md
git -C <parent-path> commit -m "task: mark <task-title> [abandoned]"
git -C <parent-path> push
```

**Release the merge-lock** — delete `<parent-path>/_millhouse/scratch/merge.lock`.

This step (lock acquire → tasks.md update → commit/push → lock release) must release the lock in ALL exit paths including errors. Use a trap/finally pattern so any failure between acquire and release still removes the lock.

### 8. Report

> "Task marked [abandoned]. Abandon protocol captured in _millhouse/task/status.md. Run mill-cleanup from the parent worktree (after closing terminals and VS Code in this worktree) to complete cleanup."

---

## Board Updates

- Abandon → task's `[phase]` marker is replaced with `[abandoned]` in parent's `tasks.md` under a merge-lock (commit + push from parent worktree).
- Worktree, branch, and children registry entry removal are deferred to `mill-cleanup`, which runs from the parent worktree in a separate invocation.
- The child's `_millhouse/task/status.md` gets a new `## Abandon` section capturing reason and context for carry-forward into the next claim of this task.
