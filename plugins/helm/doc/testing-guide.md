# Helm End-to-End Testing Guide

Test Helm in an existing repo (not millhouse). Run each step in order.

---

## 1. Setup

```
/helm-setup
```

**Verify:**
- [ ] `.kanban.md` created with 4 columns (Backlog, In Progress, Done, Blocked)
- [ ] `_helm/config.yaml` created with defaults
- [ ] `_helm/scratch/` added to `.gitignore`

---

## 2. Add tasks

```
/helm-add Fix input validation on API endpoint
/helm-add Add retry logic to database connection
```

**Verify:**
- [ ] Tasks appear in `.kanban.md` under Backlog
- [ ] kanban.md extension shows them visually
- [ ] Each task heading has `[backlog]` phase suffix (e.g. `### Fix input validation on API endpoint [backlog]`)

---

## 3. Start a task (in-place)

```
/helm-start
```

Select a task. Go through all phases: Discuss → Plan → Plan Review → Approve.

**Verify:**
- [ ] Task moved to In Progress in `.kanban.md`
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
- [ ] Task moved to Done in `.kanban.md`

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
- [ ] Worktree created at `../<repo-name>-worktrees/<slug>/`
- [ ] Branch uses `-wt-` separator (e.g. `hanf/main-wt-fix-config`)
- [ ] VS Code opens new window (via `code.cmd`)
- [ ] `_helm/scratch/status.md` in worktree has `parent:`, `task:`, `phase:`
- [ ] Handoff brief written to `_helm/scratch/briefs/handoff.md`
- [ ] Parent `.kanban.md` updated (task → In Progress with `[discussing]`)
- [ ] Worktree `.kanban.md` has only the selected task

---

## 7. Work in worktree

In the new VS Code window:

```
/helm-start
```

**Verify:**
- [ ] Reads handoff brief
- [ ] Continues from Explore phase (doesn't repeat discussion)
- [ ] Plan approved → run `/helm-go` (use `--rev 0` for doc tasks, `--rev 1` for quick tests)
- [ ] `[phase]` in `.kanban.md` heading updates through phases (implementing → testing → reviewing)
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
- [ ] `.kanban.md` conflict resolved (parent version kept)
- [ ] Verification passes
- [ ] Squash merge into parent (one commit for entire task)
- [ ] Parent `.kanban.md` updated (task → Done with `[complete]`)
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
- [ ] Parent `.kanban.md` updated (task → Backlog, `[backlog]` in heading)

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
/helm-go --rev 0
```

**Verify:**
- [ ] Code review is skipped entirely
- [ ] Goes straight from implementation to finalize

```
/helm-go --rev 5
```

**Verify:**
- [ ] Max review rounds set to 5 instead of default 3
