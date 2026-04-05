# Helm End-to-End Testing Guide

Test Helm in an existing repo (not millhouse). Run each step in order.

---

## 1. Setup

```
/helm-setup
```

**Verify:**
- [ ] `kanbans/backlog.kanban.md` created with 3 columns (Backlog, Spawn, Delete) — git-tracked
- [ ] `kanbans/board.kanban.md` created with 6 columns (Discussing, Planned, Implementing, Testing, Reviewing, Blocked) — gitignored
- [ ] `_helm/config.yaml` created with defaults
- [ ] `_helm/scratch/` added to `.gitignore`
- [ ] CLAUDE.md updated with two-board kanban section

---

## 2. Add tasks

```
/helm-add Fix input validation on API endpoint
/helm-add Add retry logic to database connection
```

**Verify:**
- [ ] Tasks appear under `## Backlog` in `kanbans/backlog.kanban.md`
- [ ] kanban.md extension shows them visually
- [ ] Backlog change committed and pushed (`add: <task-title>`)

---

## 3. Start a task (in-place)

```
/helm-start
```

Select a task. Go through all phases: Discuss → Plan → Plan Review → Approve.

**Verify:**
- [ ] Task removed from `kanbans/backlog.kanban.md` (committed: `spawn: <task-title>`)
- [ ] Task added to `## Discussing` column in `kanbans/board.kanban.md` (no `[phase]` suffix)
- [ ] After plan approval, task moved to `## Planned` column (column move, no suffix)
- [ ] Plan written to `_helm/scratch/plans/<timestamp>-<slug>.md`
- [ ] Plan has `approved: true` in frontmatter
- [ ] Plan reviewer ran and gave feedback (fixer agent applied fixes)
- [ ] `_helm/scratch/status.md` has `plan:`, `phase:`, `task:` fields

---

## 4. Execute the plan

```
/helm-go
```

**Verify:**
- [ ] Reads plan from status.md
- [ ] Checks `approved: true`
- [ ] Reads CONSTRAINTS.md (if present)
- [ ] Moves task from `## Planned` to `## Implementing` (column move)
- [ ] Implements each step with commit + push
- [ ] Moves task through columns: Implementing → Testing → Reviewing
- [ ] Code reviewer runs after implementation (fixer agent applies fixes)
- [ ] Knowledge entry written to `_helm/knowledge/`
- [ ] Task removed from `kanbans/board.kanban.md` entirely (no Done column)

---

## 5. Check status

```
/helm-status
```

**Verify:**
- [ ] Shows backlog summary (task counts: Backlog, Spawn, Delete)
- [ ] Shows work board summary (task counts: Discussing through Blocked)
- [ ] Shows current task and phase
- [ ] Shows worktree list (none if in-place)

---

## 6. Spawn a worktree

Drag a task to the Spawn column in `kanbans/backlog.kanban.md` using the kanban extension.

```
/helm-spawn
```

**Verify:**
- [ ] Task read from `## Spawn` in backlog
- [ ] Worktree created (via `helm-spawn.ps1` → `spawn-worktree.ps1`)
- [ ] VS Code opens new window
- [ ] Task removed from Spawn in backlog (committed: `spawn: <task-title>`)
- [ ] `_helm/scratch/status.md` in worktree has `parent:`, `task:`, `phase: discussing`
- [ ] Handoff brief written to `_helm/scratch/briefs/handoff.md`
- [ ] Worktree `kanbans/board.kanban.md` has task under `## Discussing`; other columns empty

---

## 7. Work in worktree

In the new VS Code window:

```
/helm-start
```

**Verify:**
- [ ] Reads handoff brief
- [ ] Continues from Explore phase (doesn't repeat discussion)
- [ ] Plan approved → run `/helm-go` (use `-r 0` for doc tasks, `-r 1` for quick tests)
- [ ] Task moves through column phases in worktree's `board.kanban.md`
- [ ] Implementation + review + knowledge works as in step 4

---

## 8. Merge worktree

From the worktree:

```
/helm-merge
```

**Verify:**
- [ ] Merge lock acquired
- [ ] Checkpoint branch created
- [ ] Parent merged into worktree first
- [ ] Verification passes
- [ ] Squash merge into parent (one commit for entire task)
- [ ] Task removed from child worktree's `kanbans/board.kanban.md` (no Done column)
- [ ] Parent's `board.kanban.md` is unaffected (independent)
- [ ] Merge lock released

Note: helm-merge cannot delete the worktree directory while VS Code has it open. Cleanup happens in step 9.

---

## 9. Cleanup worktree

Close the worktree VS Code window. Back in the parent:

```
/helm-status
```

**Verify:**
- [ ] Stale worktree detected and removed automatically
- [ ] Branch deleted (local + remote)
- [ ] Dashboard shows updated boards

---

## 10. Test abandon (optional)

Spawn a worktree, then:

```
/helm-abandon
```

**Verify:**
- [ ] Warns about uncommitted changes (if any)
- [ ] Warns about unmerged commits (if any)
- [ ] Requires explicit "abandon" confirmation
- [ ] Task read from child's `board.kanban.md` BEFORE worktree deletion
- [ ] Task added back to parent's `kanbans/backlog.kanban.md` `## Backlog` (committed: `revert: return <task> to backlog (abandoned)`)

Note: worktree directory cleanup requires closing VS Code first, then `/helm-status` from parent.

---

## 11. Test sync (optional)

Create a GitHub issue with label `helm` on the repo, then:

```
/helm-sync
```

**Verify:**
- [ ] Issue imported to `## Backlog` in `kanbans/backlog.kanban.md`
- [ ] Issue closed on GitHub
- [ ] Backlog change committed and pushed

---

## 12. Test cleanup (optional)

Drag a task to `## Delete` in backlog, then:

```
/helm-cleanup
```

**Verify:**
- [ ] Task removed from Delete column
- [ ] Backlog change committed and pushed
- [ ] Reports number of tasks cleaned

---

## 13. Test constraints (optional)

Create `CONSTRAINTS.md` in repo root with a test rule:

```markdown
# Constraints

## All variable names must use snake_case
No camelCase in Python code. This applies to all functions, variables, and parameters.
```

Run `/helm-start`, create a plan. Verify plan reviewer flags constraint violations as BLOCKING.

Delete `CONSTRAINTS.md` after testing.

---

## 14. Test -r parameter (optional)

```
/helm-go -r 0
```

**Verify:**
- [ ] Code review is skipped entirely
- [ ] Goes straight from implementation to finalize

```
/helm-go -r 2
```

**Verify:**
- [ ] Max review rounds set to 2 instead of default 5
