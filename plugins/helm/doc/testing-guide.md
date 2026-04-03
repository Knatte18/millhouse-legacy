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
- [ ] Worktree created at path from config template
- [ ] Branch created from config template
- [ ] VS Code opens new window
- [ ] `_helm/scratch/status.md` in worktree has `parent:`, `task:`, `phase:`
- [ ] Handoff brief written to `_helm/scratch/briefs/handoff.md`
- [ ] Parent `.kanban.md` updated (task → In Progress)
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
- [ ] Plan approved → run `/helm-go`
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
- [ ] Worktree merged into parent
- [ ] Parent `.kanban.md` updated (task → Done)
- [ ] Worktree removed, branch deleted
- [ ] Merge lock released

---

## 9. Test abandon (optional)

Start a task in a worktree, then:

```
/helm-abandon
```

**Verify:**
- [ ] Warns about uncommitted changes (if any)
- [ ] Warns about unmerged commits (if any)
- [ ] Requires explicit "abandon" confirmation
- [ ] Worktree removed, branch deleted
- [ ] Parent `.kanban.md` updated (task → Backlog, phase removed)

---

## 10. Test constraints (optional)

Create `CONSTRAINTS.md` in repo root with a test rule:

```markdown
# Constraints

## All variable names must use snake_case
No camelCase in Python code. This applies to all functions, variables, and parameters.
```

Run `/helm-start`, create a plan. Verify plan reviewer flags constraint violations as BLOCKING.

Delete `CONSTRAINTS.md` after testing.
