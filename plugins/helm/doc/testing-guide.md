# Helm End-to-End Testing Guide

Test Helm in an existing repo (not millhouse). Run each step in order.

---

## 1. Setup

```
/helm-setup
```

**Verify:**
- [ ] `kanbans/board.kanban.md` created with 5 columns (Backlog, Spawn, In Progress, Done, Blocked)
- [ ] `_helm/config.yaml` created with defaults
- [ ] `_helm/scratch/` added to `.gitignore`

---

## 2. Add tasks

```
/helm-add Fix input validation on API endpoint
/helm-add Add retry logic to database connection
```

**Verify:**
- [ ] Tasks appear under `## Backlog` in `kanbans/board.kanban.md`
- [ ] kanban.md extension shows them visually
- [ ] Each task heading has `[backlog]` phase suffix (e.g. `### Fix input validation on API endpoint [backlog]`)

---

## 3. Start a task (in-place)

```
/helm-start
```

Select a task. Go through all phases: Discuss → Plan → Plan Review → Approve.

**Verify:**
- [ ] Task cut from `## Backlog` column, pasted under `## In Progress` column in `kanbans/board.kanban.md`
- [ ] Phase set to `discussing`, then `planned` after approval
- [ ] Plan written to `_helm/scratch/plans/<timestamp>-<slug>.md`
- [ ] Plan has `approved: true` in frontmatter
- [ ] Plan reviewer ran and gave feedback
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
- [ ] Implements each step with commit + push
- [ ] Code reviewer runs after implementation
- [ ] Knowledge entry written to `_helm/knowledge/`
- [ ] Task cut from `## In Progress` column, pasted under `## Done` column in `kanbans/board.kanban.md`

---

## 5. Check status

```
/helm-status
```

**Verify:**
- [ ] Shows board summary (task counts per column)
- [ ] Shows current task and phase
- [ ] Shows worktree list (none if in-place)

---

## 6. Start a task (worktree)

```
/helm-start
```

Select a task, choose worktree (`-w`).

**Verify:**

- [ ] Worktree created (hub layout: sibling under hub root; non-hub: sibling of repo)
- [ ] Branch uses `-wt-` separator (e.g. `hanf/main-wt-fix-config`)
- [ ] VS Code opens new window (via `code.cmd`)
- [ ] `_git/config.yaml` in worktree has `base-branch:` and `parent-branch:`
- [ ] `_helm/scratch/status.md` in worktree has `task:`, `phase:`
- [ ] Handoff brief written to `_helm/scratch/briefs/handoff.md`
- [ ] Parent `kanbans/board.kanban.md` updated (task under `## In Progress` with `[discussing]`)
- [ ] Worktree `kanbans/board.kanban.md` has only the selected task under `## In Progress`; other columns are empty

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
- [ ] `[phase]` in `kanbans/board.kanban.md` heading updates through phases (implementing → testing → reviewing)
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
- [ ] Parent `kanbans/board.kanban.md` updated, local-only (task under `## Done` with `[complete]`)
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
- [ ] Dashboard shows updated board

---

## 10. Test abandon (optional)

Start a task in a worktree, then:

```
/helm-abandon
```

**Verify:**
- [ ] Warns about uncommitted changes (if any)
- [ ] Warns about unmerged commits (if any)
- [ ] Requires explicit "abandon" confirmation
- [ ] Parent `kanbans/board.kanban.md` updated (task under `## Backlog` with `[backlog]` in heading)

Note: worktree directory cleanup requires closing VS Code first, then `/helm-status` from parent.

---

## 11. Test constraints (optional)

Create `CONSTRAINTS.md` in repo root with a test rule:

```markdown
# Constraints

## All variable names must use snake_case
No camelCase in Python code. This applies to all functions, variables, and parameters.
```

Run `/helm-start`, create a plan. Verify plan reviewer flags constraint violations as BLOCKING.

Delete `CONSTRAINTS.md` after testing.

---

## 12. Test --rev parameter (optional)

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
