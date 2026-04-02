# Review 06 — Post-fix Verification Review

**Date:** 2026-04-03
**Scope:** All SKILL.md files, all doc/modules/, config.yaml, .kanban.md
**Branch:** helm-phase1
**Reviewer:** Fresh-eyes review, no prior context

---

## Verification of Review-05 Fixes

### B1. `.kanban.md` write-from-worktree contradiction — FIXED

kanban-format.md lines 105-111 now document the worktree-local model. helm-start step 9 writes a worktree-local board. helm-merge step 3 uses `--theirs` for `.kanban.md` conflicts. helm-abandon reads from parent's board. Consistent across all skills.

### B2. `parent:` field never written to status.md — FIXED

helm-start worktree spawn flow step 10 (SKILL.md:75-79) writes `parent:`, `task:`, and `phase:` to `_helm/scratch/status.md`.

### B3. Stale reference to `merge.md` — FIXED

No references to `merge.md` in any SKILL.md file. Confirmed via grep.

### B4. Stale reference to `skills.md` — FIXED

overview.md line 56: "Each skill is defined in `plugins/helm/skills/<name>/SKILL.md`."

### B5. Stale reference to `notifications.md` — FIXED

No references to `notifications.md` in any SKILL.md file. decisions.md references helm-go SKILL.md for notification config.

### B6. Step numbering collision in helm-go — STILL OPEN (regression)

Phase: Setup now has two entries numbered `4.`:
- Line 73: `4. **Read constraints.**`
- Line 75: `4. **Move to In Progress.**`

The fix renumbered one collision but introduced another. Should be steps 4 and 5, with Phase: Implement starting at 6.

See **C9** below.

### C1. helm-go never pushes commits — FIXED

Line 115: `git push` after step commits. Line 269: `git push` after post-review commit.

### C2. helm-start doesn't commit/push kanban changes — FIXED

Line 42 and line 48 both include `git commit && git push` after kanban moves.

### C3. No `parent:` written during worktree spawn flow — FIXED

Resolved together with B2.

### C4. helm-status infers parent from branch template — FIXED

helm-status step 3 (SKILL.md:42-44) reads `parent:` from each worktree's `status.md`.

### C5. `.kanban.md` in worktrees diverges from main repo — FIXED

Worktree-local model documented and implemented consistently.

### C6. Missing edge case: plan file not found — FIXED

helm-go Entry (SKILL.md:22): "If it does not exist, stop --- tell the user to re-run `helm-start`."

### C7. helm-merge codeguide step comment — FIXED

helm-merge line 95: "Must run BEFORE merging the worktree INTO the parent (step 6)."

### C8. helm-setup writes config then asks for branch template — FIXED

Step 3 asks for branch template (SKILL.md:44-48), step 4 writes config with user's answer (SKILL.md:50+).

### N1. Review docs reference old file names — UNCHANGED

Historical records. No action needed, as agreed.

### N2. overview.md Document Index incomplete — UNCHANGED (now worse)

See **N7** below — `validation.md` was added to the codebase but not to the Document Index.

### N3. helm-add uses `date -u` (Unix command) — UNCHANGED

Low impact. CC's bash shell handles it.

### N4. Duplicated Notification Procedure in helm-merge — FIXED

helm-merge line 166-168: "Follow the Notification Procedure defined in `helm-go` SKILL.md."

### N5. helm-go Phase: Test ordering ambiguity — FIXED

Phase setting is now the first action in Phase: Test (SKILL.md:122).

### N6. helm-start step 9 redundancy — FIXED

Line 247: "Confirm with the user that the plan is approved."

---

## New Findings

### BLOCKING

#### B7. overview.md broken link to kanban docs

**Where:** [overview.md:29](../overview.md)

**Problem:** Line 29 reads: `Details in [kanban.md](kanban.md).` There is no file `plugins/helm/doc/kanban.md`. The file was refactored to `modules/kanban-format.md`. This is a broken cross-reference in the primary architecture document.

**Fix:** Change the link to `[kanban-format.md](modules/kanban-format.md)`.

---

### CONCERN

#### C9. helm-go step numbering collision (B6 regression)

**Where:** [helm-go SKILL.md:73-75](../../skills/helm-go/SKILL.md)

**Problem:** Phase: Setup has two steps numbered `4.`:
```
4. **Read constraints.**
4. **Move to In Progress.**
```
The B6 fix resolved the original collision but created a new one. Phase: Setup should number 0-5, Phase: Implement should start at 6.

**Fix:** Renumber "Move to In Progress" to step 5. Renumber Phase: Implement start from 5 to 6. Renumber all subsequent steps accordingly (Phase: Test 7, Phase: Review 8-11, Phase: Resolve 12-16, Phase: Finalize 17-23).

---

#### C10. helm-go staleness: contradictory phase when moving to Backlog

**Where:** [helm-go SKILL.md:69](../../skills/helm-go/SKILL.md)

**Problem:** When plan is stale, the instruction says: "Update `- phase: discussing` in the task block in `.kanban.md`, move task block back to `## Backlog`." Setting `phase: discussing` while moving to Backlog is contradictory. A task in Backlog is not being discussed — the phase should be reset.

**Fix:** Change `- phase: discussing` to remove the `- phase:` line (or set `- phase: backlog`) when moving to Backlog. This matches helm-abandon's behavior (step 7: "Remove the `- phase:` line").

---

#### C11. helm-merge missing commit/push after kanban update

**Where:** [helm-merge SKILL.md:127](../../skills/helm-merge/SKILL.md)

**Problem:** Step 8 updates the parent's `.kanban.md` (move task to Done) but does not commit or push. All other kanban column-move operations in helm-start include explicit `git commit && git push`. The kanban state change is only in the working tree.

**Fix:** Add `git add .kanban.md && git commit -m "kanban: move <task> to Done" && git push` after the kanban update in step 8.

---

#### C12. helm-abandon missing commit/push after kanban update

**Where:** [helm-abandon SKILL.md:103-107](../../skills/helm-abandon/SKILL.md)

**Problem:** Step 7 updates the parent's `.kanban.md` (move task to Backlog) but does not commit or push. Same issue as C11. The CLAUDE.md instruction "Always push immediately after every commit" is violated.

**Fix:** Add `git add .kanban.md && git commit -m "kanban: move <task> to Backlog (abandoned)" && git push` after step 7.

---

### NIT

#### N7. overview.md Document Index missing validation.md

**Where:** [overview.md:58-70](../overview.md)

**Problem:** `modules/validation.md` exists but is not listed in the Document Index. This file was added as part of the review-05 fixes but the index was not updated.

**Fix:** Add `| [modules/validation.md](modules/validation.md) | Post-write validation rules for .kanban.md and config.yaml |` to the Document Index.

---

#### N8. helm-add doesn't set `- phase:` on new tasks

**Where:** [helm-add SKILL.md:40-47](../../skills/helm-add/SKILL.md)

**Problem:** helm-add creates tasks without a `- phase:` line:
```markdown
### <Title>
- created: <current UTC date>
```
But kanban-format.md's minimal task example (line 47-50) shows:
```markdown
### Add OAuth Support
- created: 2026-04-02
- phase: backlog
```
Inconsistency between what helm-add produces and what the format reference shows as "minimal."

**Fix:** Either add `- phase: backlog` to helm-add's output template, or update kanban-format.md's minimal example to omit `- phase:`. The phase is implicit from column placement, so either approach works.

---

#### N9. helm-abandon step 7 references status.md after worktree removal

**Where:** [helm-abandon SKILL.md:103](../../skills/helm-abandon/SKILL.md)

**Problem:** Step 7 says "resolve parent from `_helm/scratch/status.md` `parent:` field." But the worktree (containing status.md) was removed in step 4. The data was already read in the Entry section, so this works in practice, but the instruction is misleading — it tells the reader to resolve from a file that no longer exists.

**Fix:** Rephrase to: "Using the parent branch and task title from Entry (already read from status.md before removal)..."

---

#### N10. kanban-format.md metadata order contradicts helm-add output

**Where:** [kanban-format.md:110](../modules/kanban-format.md)

**Problem:** Line 110 prescribes: "Keep metadata lines in consistent order: priority, tags, due, phase, created." But helm-add produces `created` first (and no `phase`). The minimal task example on line 47-50 also shows `created` before `phase`, contradicting the prescribed order.

**Fix:** Align the prescribed order with actual output: either change the rule to `created, phase, priority, tags, due` (creation-first), or update helm-add and the minimal example to follow the current rule. Recommend the former — `created` is always present and `phase` is often present, so leading with those makes sense.

---

## Summary

### Review-05 Fix Verification

| ID | Severity | Status |
|----|----------|--------|
| B1 | BLOCKING | FIXED |
| B2 | BLOCKING | FIXED |
| B3 | BLOCKING | FIXED |
| B4 | BLOCKING | FIXED |
| B5 | BLOCKING | FIXED |
| B6 | BLOCKING | STILL OPEN (regression, see C9) |
| C1 | CONCERN | FIXED |
| C2 | CONCERN | FIXED |
| C3 | CONCERN | FIXED |
| C4 | CONCERN | FIXED |
| C5 | CONCERN | FIXED |
| C6 | CONCERN | FIXED |
| C7 | CONCERN | FIXED |
| C8 | CONCERN | FIXED |
| N1 | NIT | UNCHANGED (no action needed) |
| N2 | NIT | UNCHANGED (worsened, see N7) |
| N3 | NIT | UNCHANGED (no action needed) |
| N4 | NIT | FIXED |
| N5 | NIT | FIXED |
| N6 | NIT | FIXED |

### New Findings

| ID | Severity | File | Summary |
|----|----------|------|---------|
| B7 | BLOCKING | overview.md:29 | Broken link to `kanban.md` (should be `modules/kanban-format.md`) |
| C9 | CONCERN | helm-go SKILL.md:73-75 | Step numbering collision (two step 4s) — B6 regression |
| C10 | CONCERN | helm-go SKILL.md:69 | Sets `phase: discussing` when moving task to Backlog |
| C11 | CONCERN | helm-merge SKILL.md:127 | No commit/push after kanban Done update |
| C12 | CONCERN | helm-abandon SKILL.md:103-107 | No commit/push after kanban Backlog update |
| N7 | NIT | overview.md:58-70 | Document Index missing validation.md |
| N8 | NIT | helm-add SKILL.md:40-47 | No `- phase:` on new tasks (inconsistent with format reference) |
| N9 | NIT | helm-abandon SKILL.md:103 | References status.md after worktree removal |
| N10 | NIT | kanban-format.md:110 | Prescribed metadata order contradicts actual output |

### Totals

| Severity | Count |
|----------|-------|
| BLOCKING | 1 (B7) |
| CONCERN | 4 (C9-C12) |
| NIT | 4 (N7-N10) |

Most review-05 fixes are solid. The main issues are: one broken link in overview.md (blocking), a step numbering regression in helm-go, and missing commit/push after kanban updates in helm-merge and helm-abandon.
