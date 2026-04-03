# Review 05 — Full Helm Plugin Review

**Date:** 2026-04-03
**Scope:** All SKILL.md files, all doc/modules/, config.yaml, .kanban.md
**Branch:** helm-phase1
**Reviewer:** Fresh-eyes review, no prior context

---

## BLOCKING

### B1. `.kanban.md` write-from-worktree contradiction

**Where:** [kanban-format.md:105](../modules/kanban-format.md), [helm-go SKILL.md:69,75,108,222,276,461](../../skills/helm-go/SKILL.md)

**Problem:** kanban-format.md states: "`.kanban.md` lives in the repo root and is written **only from the main repo**, never from worktrees." helm-abandon and helm-merge respect this (they explicitly say "from the main repo"). But **helm-go writes to `.kanban.md` directly** at 6+ locations (move to In Progress, move to Blocked, move to Done, update phase). helm-go runs in worktrees, so this violates the stated rule.

**Fix:** Either (A) remove the "only from main repo" rule and let all skills write `.kanban.md` (it's a tracked file so worktrees have a copy), or (B) make helm-go delegate kanban writes to the main repo. Option A is simpler. The worktree has a copy of the tracked file via git. But see C5 for the divergence implication.

---

### B2. `parent:` field never written to status.md

**Where:** [helm-merge SKILL.md:27](../../skills/helm-merge/SKILL.md), [helm-start SKILL.md:244-252](../../skills/helm-start/SKILL.md), [helm-go SKILL.md:60-81](../../skills/helm-go/SKILL.md)

**Problem:** helm-merge reads `parent:` from `_helm/scratch/status.md` (line 27). worktrees.md shows `parent:` as a key field. But nobody writes it. helm-start writes `plan:`, `phase:`, and `task:` only. helm-go writes `phase:`, `current_step:`, etc. The `parent:` field is never set.

**Fix:** The worktree spawn flow in helm-start should write `parent: <parent-branch>` to `_helm/scratch/status.md` in the new worktree. Add this as part of step 8 (create _helm structure) or as a new step between 8 and 9.

---

### B3. Stale reference to `merge.md` (deleted doc)

**Where:** [helm-merge SKILL.md:11](../../skills/helm-merge/SKILL.md), [worktrees.md:87](../modules/worktrees.md)

**Problem:** helm-merge SKILL.md line 11: `For merge strategy details, see plugins/helm/doc/modules/merge.md` — file does not exist. worktrees.md line 87: `[merge.md](merge.md)` — also broken link.

**Fix:** Remove both references. The merge strategy is fully specified in helm-merge's SKILL.md itself.

---

### B4. Stale reference to `skills.md` (deleted doc)

**Where:** [overview.md:56](../overview.md)

**Problem:** `Details in [skills.md](skills.md).` — file does not exist. Skills are now individual SKILL.md files under `plugins/helm/skills/<name>/`.

**Fix:** Remove the line or replace with: "Each skill is defined in `plugins/helm/skills/<name>/SKILL.md`."

---

### B5. Stale reference to `notifications.md` (deleted doc)

**Where:** [worktrees.md:104](../modules/worktrees.md), [decisions.md:72](../decisions.md)

**Problem:** worktrees.md: `Canonical format defined in [notifications.md](notifications.md)` — file does not exist. decisions.md: `Specified in notifications.md` — same. The notification procedure is now inline in helm-go SKILL.md.

**Fix:** worktrees.md: change to "Format defined in helm-go SKILL.md." decisions.md: change to "Specified in helm-go SKILL.md."

---

### B6. Step numbering collision in helm-go

**Where:** [helm-go SKILL.md:75,85](../../skills/helm-go/SKILL.md)

**Problem:** Phase: Setup ends with step 5 ("Move to In Progress"). Phase: Implement starts with step 5 ("For each step in the plan"). Two different steps share the same number.

**Fix:** Renumber. Setup should end at step 4, Implement starts at 5.

---

## CONCERN

### C1. helm-go never pushes commits

**Where:** [helm-go SKILL.md](../../skills/helm-go/SKILL.md) (entire file — no `git push` anywhere)

**Problem:** helm-go commits after each step (line 112-115) but never pushes. CLAUDE.md says "Always push immediately after every commit." Without pushes, if the session crashes, committed work is only local and unrecoverable from another machine.

**Fix:** Add `git push` after each step commit.

---

### C2. helm-start doesn't commit/push kanban changes

**Where:** [helm-start SKILL.md:42](../../skills/helm-start/SKILL.md)

**Problem:** helm-start moves the task to In Progress and edits `.kanban.md`, but never commits or pushes the kanban change. If a second worktree reads `.kanban.md`, it won't see the move.

**Fix:** Commit and push the kanban change after moving the task.

---

### C3. No `parent:` written during worktree spawn flow

**Where:** [helm-start SKILL.md:66-84](../../skills/helm-start/SKILL.md)

**Problem:** The worktree spawn flow creates `_helm/scratch/` and writes the handoff brief, but never writes `_helm/scratch/status.md` with the `parent:` field. When helm-merge runs later, it can't find the parent branch. Related to B2 but specific to the spawn flow.

**Fix:** Add a step to write `status.md` with `parent: <parent-branch>` and `task: <task-title>` in the new worktree.

---

### C4. helm-status infers parent from branch template — fragile

**Where:** [helm-status SKILL.md:43](../../skills/helm-status/SKILL.md)

**Problem:** "read `_helm/config.yaml` `worktree.branch-template` to infer parent from branch name, or fall back to `main`." Reverse-engineering a branch template to extract the parent slug is fragile, especially with simple templates like `"{slug}"` where there's no parent segment at all.

**Fix:** Read `parent:` from each worktree's `_helm/scratch/status.md` instead (once B2/C3 are fixed).

---

### C5. `.kanban.md` in worktrees diverges from main repo

**Problem:** `.kanban.md` is tracked (not gitignored). When a worktree writes to it (helm-go), the change lives on the worktree branch only. The main repo's `.kanban.md` is stale until merge. Other worktrees have their own stale copies. There's no synchronization mechanism.

**Fix:** Needs a design decision. Options: (A) Move `.kanban.md` writes to the main repo only (requires mechanism for helm-go to reach main repo), (B) Accept divergence and reconcile on merge, (C) Gitignore `.kanban.md` and treat it as scratch (breaks the kanban.md VS Code extension on main). Interacts with B1.

---

### C6. Missing edge case: plan file not found

**Where:** [helm-go SKILL.md:20-23](../../skills/helm-go/SKILL.md)

**Problem:** helm-go reads `plan:` from status.md and reads the file. If the plan file was deleted (e.g., `_helm/scratch/` cleaned up), there's no error handling — just "check `approved: true`."

**Fix:** Add: "If the plan file does not exist, stop and tell the user to re-run `helm-start`."

---

### C7. helm-merge codeguide step comment is confusing

**Where:** [helm-merge SKILL.md:90-95](../../skills/helm-merge/SKILL.md)

**Problem:** Step 5 says "Must run BEFORE the merge to parent." True (step 6 is the merge to parent). But there's already a merge in step 3 (parent INTO worktree). The comment could be misread as "before step 3."

**Fix:** Clarify: "Must run BEFORE merging the worktree INTO the parent (step 6)."

---

### C8. helm-setup writes config then asks for branch template

**Where:** [helm-setup SKILL.md:42-85](../../skills/helm-setup/SKILL.md)

**Problem:** Step 3 writes `_helm/config.yaml` with default `branch-template: "{slug}"`. Step 5 asks the user and updates it. Config is written twice. If step 5 is interrupted, the config has the wrong template.

**Fix:** Collect all user inputs first, then write config once.

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

### N4. Duplicated Notification Procedure in helm-merge

**Where:** [helm-merge SKILL.md:164-187](../../skills/helm-merge/SKILL.md)

**Problem:** The entire notification procedure is copy-pasted from helm-go. If the procedure changes, both files must be updated independently.

**Fix:** Reference helm-go's version instead of duplicating: "Follow the Notification Procedure defined in helm-go SKILL.md."

---

### N5. helm-go Phase: Test ordering ambiguity

**Where:** [helm-go SKILL.md:119-131](../../skills/helm-go/SKILL.md)

**Problem:** Phase: Test sets `- phase: testing` after describing the verification step. Should be set as the first action in the phase (to accurately reflect state before running verification).

**Fix:** Move `Set - phase: testing` to the first line of Phase: Test.

---

### N6. helm-start step 9 redundancy

**Where:** [helm-start SKILL.md:238](../../skills/helm-start/SKILL.md)

**Problem:** Step 9 says "present the final plan to the user" but the user has been reviewing it through the plan review loop already.

**Fix:** Rephrase to "Confirm with the user that the plan is approved."

---

## Lifecycle Coverage

Checked the full lifecycle: task created (helm-add) -> discussed (helm-start) -> planned (helm-start) -> implemented (helm-go) -> reviewed (helm-go) -> merged (helm-merge). Also covers: abandon (helm-abandon), status (helm-status), sync (helm-sync), setup (helm-setup).

**Gaps:**
- No skill for "unblock" — when a blocked task is resolved, the user must manually edit `.kanban.md` to move it back to In Progress. Minor — could be handled ad hoc.
- No skill for editing an existing task (change title, add description, reprioritize). Must edit `.kanban.md` manually. Minor.

---

## Summary

| Severity | Count |
|----------|-------|
| BLOCKING | 6 |
| CONCERN | 8 |
| NIT | 6 |

The blocking issues are all fixable without architectural changes. B1/C5 (kanban write rules + divergence) are the most significant and require a design decision. B2/C3 (`parent:` field) are straightforward additions. B3-B5 are stale references from the doc refactor. B6 is a typo-level fix.
