# Review 05 — Full Helm Plugin Review

**Date:** 2026-04-03
**Scope:** All SKILL.md files, all doc/modules/, config.yaml, .kanban.md
**Branch:** helm-phase1
**Reviewer:** Fresh-eyes review, no prior context

---

## BLOCKING

### B1. `.kanban.md` write-from-worktree contradiction — RESOLVED

**Where:** [kanban-format.md:105](../modules/kanban-format.md), [helm-go SKILL.md](../../skills/helm-go/SKILL.md)

**Problem:** kanban-format.md stated "only from the main repo, never from worktrees" but helm-go writes to `.kanban.md` from worktrees.

**Resolution:** Adopted worktree-local model. Each worktree has its own `.kanban.md`. Parent has full board, task worktree has only its task. On merge, parent's version wins (`.kanban.md` conflict resolved with `--theirs`), then parent's board is updated. Updated: kanban-format.md, helm-go, helm-merge, helm-abandon, helm-start.

---

### B2. `parent:` field never written to status.md — RESOLVED

**Resolution:** Added step 10 in helm-start worktree spawn flow: writes `_helm/scratch/status.md` with `parent:`, `task:`, and `phase:` fields. Also updated helm-status and helm-abandon to read `parent:` from status.md.

---

### B3. Stale reference to `merge.md` (deleted doc) — RESOLVED

**Resolution:** Removed both references from helm-merge SKILL.md and worktrees.md.

---

### B4. Stale reference to `skills.md` (deleted doc) — RESOLVED

**Resolution:** Replaced with "Each skill is defined in `plugins/helm/skills/<name>/SKILL.md`." in overview.md.

---

### B5. Stale reference to `notifications.md` (deleted doc) — RESOLVED

**Resolution:** Updated worktrees.md and decisions.md to reference helm-go SKILL.md instead.

---

### B6. Step numbering collision in helm-go — RESOLVED

**Resolution:** Renumbered Setup step 5 to step 4. Implement starts at 5.

---

## CONCERN

### C1. helm-go never pushes commits — RESOLVED

**Resolution:** Added `git push` after step commits and post-review commit in helm-go.

---

### C2. helm-start doesn't commit/push kanban changes — RESOLVED

**Resolution:** Added commit+push after kanban move in both in-place and worktree spawn flows.

---

### C3. No `parent:` written during worktree spawn flow — RESOLVED

**Resolution:** Resolved together with B2. New step 10 in worktree spawn flow writes status.md.

---

### C4. helm-status infers parent from branch template — fragile — RESOLVED

**Resolution:** Updated helm-status to read `parent:` from each worktree's status.md instead of parsing branch template.

---

### C5. `.kanban.md` in worktrees diverges from main repo — RESOLVED

**Resolution:** Resolved together with B1. Worktree-local model accepts divergence by design. Task worktrees have a minimal board (only their task). On merge, parent's version wins and is then updated. No synchronization needed — each worktree only cares about its own task.

---

### C6. Missing edge case: plan file not found — RESOLVED

**Resolution:** Added "If it does not exist, stop" check in helm-go Entry section.

---

### C7. helm-merge codeguide step comment is confusing — RESOLVED

**Resolution:** Clarified to "Must run BEFORE merging the worktree INTO the parent (step 6)."

---

### C8. helm-setup writes config then asks for branch template — RESOLVED

**Resolution:** Reordered: step 3 asks for branch template, step 4 writes config with user's answer.

---

## NIT

### N1. Review docs in `doc/reviews/` reference old file names

**Where:** Multiple files in `plugins/helm/doc/reviews/`

**Problem:** Historical review results reference `skills.md`, `failures.md`, `notifications.md`, `reviews.md`, `kanban.md` (as doc files). These are old names from before the refactor into individual SKILL.md files.

**Fix:** No action needed — these are historical records. Consider adding a note at the top of the reviews directory if it confuses contributors.

---

### N2. overview.md Document Index incomplete

**Where:** [overview.md:58-70](../overview.md)

**Problem:** The Document Index doesn't list `TODO.md` or the `reviews/` subdirectory.

**Fix:** Low priority. Add entries if desired.

---

### N3. helm-add uses `date -u` (Unix command)

**Where:** [helm-add SKILL.md:38](../../skills/helm-add/SKILL.md)

**Problem:** `date -u +%Y-%m-%d` is a Unix command. The user's environment is PowerShell. CC runs bash via Git Bash on Windows so this works, but it's inconsistent with the instruction "always use PowerShell syntax."

**Fix:** Low impact — CC's bash shell handles it. Note if desired.

---

### N4. Duplicated Notification Procedure in helm-merge — RESOLVED

**Resolution:** Replaced inline copy with reference to helm-go SKILL.md.

---

### N5. helm-go Phase: Test ordering ambiguity — RESOLVED

**Resolution:** Moved phase setting to first action in Phase: Test.

---

### N6. helm-start step 9 redundancy — RESOLVED

**Resolution:** Rephrased to "Confirm with the user that the plan is approved."

---

## Lifecycle Coverage

Checked the full lifecycle: task created (helm-add) -> discussed (helm-start) -> planned (helm-start) -> implemented (helm-go) -> reviewed (helm-go) -> merged (helm-merge). Also covers: abandon (helm-abandon), status (helm-status), sync (helm-sync), setup (helm-setup).

**Gaps:**
- No skill for "unblock" — when a blocked task is resolved, the user must manually edit `.kanban.md` to move it back to In Progress. Minor — could be handled ad hoc.
- No skill for editing an existing task (change title, add description, reprioritize). Must edit `.kanban.md` manually. Minor.

---

## Summary

| Severity | Count | Resolved |
|----------|-------|----------|
| BLOCKING | 6 | 6 |
| CONCERN | 8 | 8 |
| NIT | 6 | 4 (N1-N3 unchanged, N4-N6 resolved) |

All blocking and concern issues resolved. B1/C5 resolved with worktree-local kanban model. Remaining unresolved NITs (N1-N3) are cosmetic or informational.
