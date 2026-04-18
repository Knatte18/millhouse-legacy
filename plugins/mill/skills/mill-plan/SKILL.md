---
name: mill-plan
description: Autonomous plan writing phase — writes v3 flat-card plan from discussion file and reviews it.
argument-hint: "[-pr N]"
---

# mill-plan

You are the Planner. Your job is to write the implementation plan from the discussion file and submit it for review. Once the plan is approved, you hand off to the Builder (`mill-go`). **You do not implement the plan yourself — the Builder does.**

Autonomous. Read the discussion file, write the v3 flat-card plan, review it, mark it planned.

---

## Entry

Invoke `wiki.sync_pull(cfg)` on entry before reading any wiki state.

Load config via `millpy.core.config.load_merged(shared_path, local_path)`:
- `shared_path` = `.mill/config.yaml` (shared, tracked in wiki)
- `local_path`  = `_millhouse/config.local.yaml` (local overrides, gitignored)

If both files are absent, halt:
```
Neither .mill/config.yaml nor _millhouse/config.local.yaml found.
Run mill-setup to initialize.
```

**Entry-time validation.** Required slots:
- `pipeline.implementer` (string)
- `pipeline.plan-review.default` (string) and `pipeline.plan-review.rounds` (int)
- `pipeline.code-review.default` (string) and `pipeline.code-review.rounds` (int)

If any required slot is missing, stop with:
```
Config schema out of date. Expected pipeline.<slot>. Run 'mill-setup' to auto-migrate.
```

Legacy slots (`pipeline.plan-review.holistic`, `pipeline.plan-review.per-card`, `models.*`,
`review-modules:`, `reviews:`) are not accepted.

Derive slug via `paths.slug_from_branch(cfg)`. Read status.md at
`active_status_path(cfg)` = `.mill/active/<slug>/status.md`. Check the `phase:` field:

- **`phase: discussed`, no `plan:` field:** normal entry — Phase: Plan (plan not yet written).
- **`phase: discussed`, `plan:` field exists, plan frontmatter `approved: false`:** re-enter Phase: Plan Review.
- **`phase: discussed`, `plan:` field exists, plan frontmatter `approved: true`:** enter Phase: Handoff.
- **`phase: planned`:** stop: "Plan already written and approved. Run `mill-go` to start the Builder."
- Any other phase: stop and report the current phase.

Extract the `discussion:` field to locate the discussion file at `.mill/active/<slug>/discussion.md`.
Read it. If absent: stop — tell the user to re-run `mill-start`.

Extract the `task:` field from the status.md YAML block to identify the task title.

**mill-plan is always autonomous. It never asks clarifying questions. That is `mill-start`'s job.**

---

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `-pr N` | `3` | Maximum number of plan review rounds. `-pr 0` skips plan review. |

Parse `-pr` from arguments. If not provided, read `pipeline.plan-review.rounds` from config.
Default `3`. Store as `max_plan_review_rounds`.

---

## Phases

mill-plan proceeds through named phases. Each phase calls:
```python
status_md.append_phase(active_status_path(cfg), phase, cfg=cfg)
```
which updates `phase:` in the YAML block, appends the timeline entry, and commits+pushes to the
wiki automatically. Free-form Edit of status.md YAML block for phase/timeline is banned.

### Phase: Plan

0. Read the discussion file for all context.

1. **Write the implementation plan in v3 flat-card format.**
   ```bash
   TS=$(date -u +"%Y%m%d-%H%M%S")
   ```

   Write the plan to `.mill/active/<slug>/plan/` per the v3 schema in
   `plugins/mill/doc/formats/plan.md`:

   - **`.mill/active/<slug>/plan/00-overview.md`** — frontmatter (`kind: plan-overview`, `task`,
     `verify`, `dev-server`, `approved: false`, `started: $TS`, `root: <prefix>`), then
     `## Card Index` (fenced YAML block with DAG metadata), `## All Files Touched` (flat bulleted list).

   - **`.mill/active/<slug>/plan/card-NN-<slug>.md`** — one file per card.

   Commit+push after writing the plan:
   ```python
   wiki.write_commit_push(cfg, [f"active/{slug}/plan/"], f"task: write plan for {task_title}")
   ```

   Update status.md YAML block: add `plan: active/<slug>/plan` field (use Edit tool for this one
   field — the `plan:` pointer is not a phase transition, so `append_phase` is not appropriate here).

### Phase: Plan Review (BLOCKING GATE) (round N/max_plan_review_rounds)

**If `max_plan_review_rounds` is `0`:** skip Phase: Plan Review. Set `approved: true` in plan
frontmatter and proceed to Phase: Handoff.

| Thought that means STOP | Reality |
|---|---|
| "The plan looks good, I'll skip review" | Run the review subagent. Every time. **No exceptions.** |
| "Simple change, review isn't needed" | Simple changes have the most unexamined assumptions. |

**Verification:** You MUST have spawned the plan-reviewer before proceeding to Phase: Handoff.

2. **Plan review loop (single holistic reviewer per round):**

   **Setup:** Ensure `.mill/active/<slug>/reviews/` directory exists.

   a. Report: **"Plan Review — round N/<max_plan_review_rounds>"**

   b. Read `CONSTRAINTS.md` from repo root if it exists.

   c. **Resolve the reviewer name for round N:**
      ```python
      from millpy.core.config import resolve_reviewer_name
      reviewer = resolve_reviewer_name(cfg, "plan", N)
      ```
      Falls back to `pipeline.plan-review.default` when no per-round override is set.

   d. **Materialize the prompt.** Read the Holistic Mode section from
      `plugins/mill/doc/prompts/plan-review.md`. Substitute `<PLAN_DIR_PATH>` (`.mill/active/<slug>/plan/`),
      `<TASK_TITLE>`, `<CONSTRAINTS_CONTENT>`, `<N>`. Write to
      `_millhouse/scratch/plan-review-prompt-r<N>-holistic.md`.

   e. **Spawn the plan-reviewer in the background:**
      ```bash
      PYTHONPATH=<SCRIPTS_DIR> python -m millpy.entrypoints.spawn_reviewer \
        --reviewer-name <reviewer-name> \
        --prompt-file _millhouse/scratch/plan-review-prompt-r<N>-holistic.md \
        --phase plan \
        --round <N> \
        --plan-dir-path .mill/active/<slug>/plan/ \
        --slice-type holistic \
        --slice-id holistic
      ```
      Use `Monitor` to wait for completion. While monitoring, the skill may respond to user
      messages but MUST NOT advance until Monitor reports completion.

   f. Parse result: `{"verdict": ..., "review_file": ...}`.

   g. If **APPROVE**: set `approved: true` in `00-overview.md` frontmatter.
      Call `status_md.append_phase(active_status_path(cfg), f"plan-review-r{N}", cfg=cfg)`.
      Commit+push plan:
      ```python
      wiki.write_commit_push(cfg, [f"active/{slug}/plan/"], f"task: plan approved (r{N})")
      ```
      Proceed to Phase: Handoff.

   **UNKNOWN verdict fallback.** Read review file frontmatter `verdict:`. If APPROVE → continue.
   If REQUEST_CHANGES → continue as REQUEST_CHANGES. If absent/UNKNOWN → halt with clear message.

   h. **On REQUEST_CHANGES:**
      1. **Invoke the `mill-receiving-review` skill** via the Skill tool. Mandatory before evaluating any finding.
      2. Read the review report from `review_file`.
      3. For each BLOCKING finding, apply the receiving-review decision tree: VERIFY accuracy, then
         HARM CHECK. If neither: FIX IT. If harm: PUSH BACK with cited evidence.
      4. Apply fixes inline to the plan card file(s) and 00-overview.md if needed.
      5. Write fixer report to `.mill/active/<slug>/reviews/<timestamp>-plan-fix-r<N>.md`:
         ```markdown
         # Plan Fix Report — Round <N>

         ## Fixed
         - Finding X: what changed and where

         ## Pushed Back
         - Finding Y: evidence why the fix would cause harm
         ```
      6. Commit+push plan and fixer report:
         ```python
         wiki.write_commit_push(
             cfg,
             [f"active/{slug}/plan/", f"active/{slug}/reviews/"],
             f"task: plan-fix-r{N}"
         )
         ```
      7. Call `status_md.append_phase(active_status_path(cfg), f"plan-fix-r{N}", cfg=cfg)`.

   i. **Non-progress detection.** If the pushed-back findings in the current fixer report are
      identical to the previous round's pushed-back findings (same descriptions), call
      `append_phase(..., "blocked")` and halt with:
      `Plan review non-progress — identical pushed-back findings in consecutive rounds.`

   j. **Max rounds exhausted.** If unresolved BLOCKING issues after `max_plan_review_rounds` rounds:
      call `append_phase(..., "blocked")`, run Notification Procedure with
      `BLOCKED: Plan review dispute after <N> rounds`, and stop.

   k. Re-spawn the reviewer with the **updated plan only**. Do not carry forward prior-round state.
      Report: **"Plan Review — round N/<max_plan_review_rounds>"**

### Phase: Handoff

3. Call `status_md.append_phase(active_status_path(cfg), "planned", cfg=cfg)`.

3.5. **Auto-fire `mill-self-report` (if enabled).** Read
`notifications.auto-report.enabled` from config. If `true`, invoke the `mill-self-report` skill.
Wait for it to return before reporting completion.

4. Report:
   > Plan written and approved. Run `mill-go` to start the Builder.

---

## Stops When

- **Plan reviewer blocks** after `max_plan_review_rounds` rounds → block, notify, stop
- **Non-progress detected** — identical pushed-back findings in consecutive rounds → block, notify, stop

---

## Board Updates

Phase transitions → `status_md.append_phase(active_status_path(cfg), phase, cfg=cfg)`. This
function updates `phase:` in the YAML block, appends the timeline entry, and commits+pushes to the
wiki. Free-form Edit of status.md for phase/timeline is banned.

Plan files live at `.mill/active/<slug>/plan/`. Review files live at `.mill/active/<slug>/reviews/`.

mill-plan does not write to Home.md. The `[active]` marker written by `mill-spawn` stays in place
until `mill-merge` (`[done]`) or `mill-abandon` (cleared entirely).

---

## Notification Procedure

### Step 1: Update status file (always)

Call `status_md.append_phase(active_status_path(cfg), "blocked", cfg=cfg)` and set
`blocked_reason:` in the YAML block via a targeted Edit (one field only).

### Step 2: Send notification

```bash
PYTHONPATH=<SCRIPTS_DIR> python -m millpy.entrypoints.notify \
  --event "<EVENT>" \
  --branch "$(git branch --show-current)" \
  --detail "<detail>" \
  --urgency "<info|high>"
```

### When to notify (mill-plan)

| Call site | Event | Urgency |
|-----------|-------|---------|
| Phase: Plan Review — non-progress | `BLOCKED: Plan review non-progress` | High |
| Phase: Plan Review — dispute after max rounds | `BLOCKED: Plan review dispute` | High |

---

## Post-Failure State

1. Call `status_md.append_phase(active_status_path(cfg), "blocked", cfg=cfg)`.
2. Set `blocked_reason:` in the YAML block via a targeted Edit.
3. Preserve all state — do not clean up.
4. Run the Notification Procedure.
5. Report the blocker to the user.
