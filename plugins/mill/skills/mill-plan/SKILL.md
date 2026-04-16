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

Read `_millhouse/config.yaml`. If it does not exist, stop — tell the user to run `mill-setup` first.

**Entry-time validation.** Validate `_millhouse/config.yaml`. Required slots under the `pipeline:` block:
- `pipeline.implementer` (string)
- `pipeline.plan-review.holistic` (string) — reviewer name for holistic mode
- `pipeline.plan-review.per-card` (string) — reviewer name for per-card mode
- `pipeline.plan-review.rounds` (int)
- `pipeline.code-review.default` (string) and `pipeline.code-review.rounds` (int)

If any required slot is missing, stop with:
```
Config schema out of date. Expected pipeline.<slot>. Run 'mill-setup' to auto-migrate.
```

Legacy slots (`models.session`, `models.explore`, `models.<phase>-review`, `review-modules:`, `reviews:`) are not accepted. The `pipeline:` block is the only config schema.

Read `_millhouse/task/status.md`. Check the `phase:` field:

- **`phase: discussed`, no `plan:` field in status.md:** normal entry — Phase: Plan (plan not yet written).
- **`phase: discussed`, `plan:` field exists, plan frontmatter has `approved: false`:** Phase: Plan Review (plan written, not yet approved). Re-enter the plan review loop with the existing plan.
- **`phase: discussed`, `plan:` field exists, plan frontmatter has `approved: true`:** plan approved but phase not updated — enter Phase: Handoff.
- **`phase: planned`:** plan already approved and phase written. Stop: "Plan already written and approved. Run `mill-go` to start the Builder."
- Any other phase: stop and report the current phase.

Extract the `discussion:` field from the YAML code block to locate the discussion file. Read it. If it does not exist, stop — tell the user to re-run `mill-start`.

Read the discussion file frontmatter. Validate the `worktree:` field matches the current working directory (`git rev-parse --show-toplevel`). If they differ, warn: "mill-plan is running from `<cwd>` but the discussion was written in `<worktree>`. Verify you are in the correct worktree." This is the one exception to the "never ask" rule — worktree mismatch can destroy work.

Extract the `task:` field from the YAML code block in status.md to identify the task title.

**mill-plan is always autonomous. It never asks clarifying questions. That is `mill-start`'s job.**

**Never ask for permission or confirmation during execution.**

---

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `-pr N` | `3` | Maximum number of plan review rounds. `-pr 0` skips plan review entirely. |

Parse `-pr` from the skill invocation arguments. If not provided via CLI, read `pipeline.plan-review.rounds` from `_millhouse/config.yaml`. CLI args override config. Default `3`. Store as `max_plan_review_rounds`.

---

## Phases

mill-plan proceeds through named phases. Each phase updates the YAML code block in `_millhouse/task/status.md` with the current phase name and relevant fields, and inserts timeline entries before the closing ` ``` ` of the timeline text block.

### Phase: Plan

0. Read the discussion file for all context: problem, approach, decisions, constraints, technical context, testing strategy, Q&A log, config.

1. **Write the implementation plan in v3 flat-card format.** Generate the timestamp via shell (see `@mill:cli` timestamp rules — never guess timestamps):
   ```bash
   TS=$(date -u +"%Y%m%d-%H%M%S")
   ```
   Use `$TS` for the `started:` frontmatter field.

   **Compute `root:`** — Find the longest common path prefix across all file paths the plan will touch. For example, if all files live under `plugins/mill/scripts/millpy`, then `root: plugins/mill/scripts/millpy`. If no single common prefix exists (files span multiple top-level directories), set `root:` to empty string. All paths in the Card Index and card files are root-relative when `root:` is non-empty; full repo-relative paths when `root:` is empty string.

   Write the plan to `_millhouse/task/plan/` per the v3 schema in `plugins/mill/doc/formats/plan.md`:

   - **`_millhouse/task/plan/00-overview.md`** — frontmatter (`kind: plan-overview`, `task`, `verify`, `dev-server`, `approved: false`, `started: $TS`, `root: <prefix>`), then `## Card Index` (fenced YAML block with DAG metadata), `## All Files Touched` (flat bulleted list, root-relative paths).

     The `## Card Index` YAML block schema:
     ```yaml
     <card-number>:
       slug: <card-slug>
       creates: [<root-relative-path>, ...]
       modifies: [<root-relative-path>, ...]
       reads: [<root-relative-path>, ...]
       depends-on: [<card-number>, ...]
     ```

   - **`_millhouse/task/plan/card-NN-<slug>.md`** — one file per card. Filename: two-digit prefix `NN` matching the card number, hyphenated slug. Frontmatter: `kind: plan-card`, `card-number`, `card-slug`. Body: a single step card using the v2 step card schema (see `plugins/mill/doc/formats/plan.md`). Paths in `Creates:`, `Modifies:`, `Reads:` are root-relative when `root:` is non-empty.

   **Decompose the work into cards.** Each card is a single atomic step — one cohesive unit that a fresh agent can implement from the card alone. Cards must declare their `depends-on` field. Card numbers are globally sequential starting at 1, no gaps.

   **Each card must satisfy the atomicity invariant** — the extraction test in `plugins/mill/doc/formats/plan.md` must pass for every card. Verbosity is the feature; repetition is acceptable when it lets a fresh agent implement one card without reading another.

   **Card Index consistency rules:**
   - `reads:` in the Card Index must exactly match the `Reads:` field in the card file body.
   - `depends-on:` references must point to lower-numbered cards (no forward references).
   - `creates:` and `modifies:` must not both be empty for any card.
   - All paths in `Explore:` in the card body must also appear in `Reads:`.

   Write the full plan autonomously — no incremental approval checkpoints.

   Update the YAML code block in status.md: add `plan: _millhouse/task/plan` (directory path, no `.md` suffix).

### Phase: Plan Review (BLOCKING GATE) (round N/max_plan_review_rounds)

**If `max_plan_review_rounds` is `0`:** skip Phase: Plan Review entirely. Set `approved: true` in plan frontmatter and proceed to Phase: Handoff.

| Thought that means STOP | Reality |
|---|---|
| "The plan looks good, I'll skip review" | Run the review subagent. Every time. **No exceptions.** |
| "This is a simple change, review isn't needed" | Simple changes have the most unexamined assumptions. Review anyway. |
| "I'll save time and go straight to Handoff" | Time saved here is bugs shipped later. Run the gate. |

**Verification:** You MUST have spawned the plan-reviewer before proceeding to Phase: Handoff. If you have not, go back and run Phase: Plan Review now.

2. **Plan review loop (v3 parallel fan-out — N per-card + 1 holistic):**

   **Setup:** Ensure `_millhouse/task/reviews/` directory exists (`mkdir -p` if not). Read card numbers from the Card Index:
   ```python
   from pathlib import Path
   from millpy.core.plan_io import resolve_plan_path, read_card_index
   task_dir = Path("_millhouse/task")
   loc = resolve_plan_path(task_dir)
   card_index = read_card_index(loc)
   card_numbers = sorted(card_index.keys())
   ```

   Instantiate the loop object **once** before the first round:
   ```python
   from millpy.core.plan_review_loop import PlanReviewLoop, PlanOverviewV3
   loop = PlanReviewLoop(PlanOverviewV3(card_numbers=card_numbers), max_rounds=max_plan_review_rounds)
   ```

   **v3 parallel fan-out:**

   a. Report to user: **"Plan Review — round N/&lt;max_plan_review_rounds&gt;"**

   b. Read `CONSTRAINTS.md` from repo root (via `git rev-parse --show-toplevel`) if it exists.

   c. **Resolve the per-card reviewer name** via:
      ```python
      from millpy.core.config import load, resolve_reviewer_name
      cfg = load(Path("_millhouse/config.yaml"))
      per_card_reviewer = resolve_reviewer_name(cfg, "plan", N, slice_type="per-card")
      holistic_reviewer = resolve_reviewer_name(cfg, "plan", N, slice_type="holistic")
      ```

   d. **Advance the loop and spawn all reviewers in parallel.** Call `slices = loop.next_round_plan()` to increment the round counter and obtain the slice list (`["card-1", "card-2", ..., "holistic"]`). Use `run_in_background: true` for all but the last reviewer, then Monitor each.

      **Per-card reviewers** — one per card in the plan:

      For each card number `<card_number>` in `card_numbers`:
      1. Read the Per-Card Mode section from `plugins/mill/doc/prompts/plan-review.md`.
      2. Substitute `<CARD_NUMBER>` (the card number as an integer string), `<PLAN_CARD_PATH>` (relative path to the card file, e.g. `_millhouse/task/plan/card-NN-<slug>.md`), `<TASK_TITLE>`, `<CONSTRAINTS_CONTENT>`, and `<N>`.
      3. **Construct `<FILES_PAYLOAD>`:** The payload contains the card file plus all files listed in the card's `reads:` field (resolved to full repo-relative paths). Format:
         ```
         === _millhouse/task/plan/card-NN-<slug>.md ===

         <card file content>

         === <full-path-of-reads-file-1> ===

         <reads file 1 content>

         === <full-path-of-reads-file-2> ===

         <reads file 2 content>
         ```
         Use `plan_io.resolve_path(loc, relative_path)` to convert root-relative reads paths to full repo-relative paths. If a reads file does not exist, note `(file not found)` as its content.
      4. Substitute `<FILES_PAYLOAD>` into the prompt.
      5. Write materialized prompt to `_millhouse/scratch/plan-review-prompt-r<N>-card-<card_number>.md`.

      ```bash
      (cd plugins/mill/scripts && python -m millpy.entrypoints.spawn_reviewer) \
        --reviewer-name <per-card-reviewer-name> \
        --prompt-file _millhouse/scratch/plan-review-prompt-r<N>-card-<card_number>.md \
        --phase plan \
        --round <N> \
        --plan-overview _millhouse/task/plan/00-overview.md \
        --plan-batch _millhouse/task/plan/card-NN-<slug>.md \
        --slice-type per-card \
        --slice-id card-<card_number>
      ```

      **Holistic reviewer** (exactly one):
      1. Read the Holistic Mode section from `plugins/mill/doc/prompts/plan-review.md`.
      2. Substitute `<PLAN_DIR_PATH>` (`_millhouse/task/plan/`), `<TASK_TITLE>`, `<CONSTRAINTS_CONTENT>`, `<N>`.
      3. Write to `_millhouse/scratch/plan-review-prompt-r<N>-holistic.md`.

      ```bash
      (cd plugins/mill/scripts && python -m millpy.entrypoints.spawn_reviewer) \
        --reviewer-name <holistic-reviewer-name> \
        --prompt-file _millhouse/scratch/plan-review-prompt-r<N>-holistic.md \
        --phase plan \
        --round <N> \
        --plan-dir-path _millhouse/task/plan/ \
        --slice-type holistic \
        --slice-id holistic
      ```

      Collect each result: `{"verdict": ..., "review_file": ...}`.

   e. **Collect verdicts and advance the loop.** Build a `verdicts` dict mapping each slice_id (e.g. `"card-1"`, `"card-2"`, `"holistic"`) to its verdict (`"APPROVE"` or `"REQUEST_CHANGES"`). If all slices approved:
      ```python
      outcome = loop.record_round_result(verdicts, fixer_report_path=None)
      # outcome == "APPROVED" → step 2f
      ```
      If any slice rejected, proceed to step 2h to apply fixes and write the fixer report, then:
      ```python
      outcome = loop.record_round_result(verdicts, fixer_report_path)
      # outcome is one of: "APPROVED", "CONTINUE", "BLOCKED_NON_PROGRESS", "BLOCKED_MAX_ROUNDS"
      ```

   f. **On `outcome == "APPROVED"`:** set `approved: true` in `_millhouse/task/plan/00-overview.md` frontmatter. Insert `plan-review-r<N>  <timestamp>` before the closing ` ``` ` of the timeline text block. Proceed to Phase: Handoff.

   g. **UNKNOWN verdict fallback (C.2).** If any slice returns `UNKNOWN`, read the slice's review file and parse its YAML frontmatter `verdict:` field (case-insensitive). If APPROVE, treat as APPROVE. If REQUEST_CHANGES, treat as REQUEST_CHANGES. If absent or UNKNOWN, halt: `Plan reviewer verdict is UNKNOWN and review file frontmatter is unparseable. Halting; manual intervention required.`

   h. **On any slice returning `"REQUEST_CHANGES"`:** For each slice whose verdict is `"REQUEST_CHANGES"`:
      1. **Invoke the `mill-receiving-review` skill** via the Skill tool. This is mandatory before evaluating any finding — it loads the decision tree you must apply.
      2. Read the review report from that slice's `review_file`.
      3. For each BLOCKING finding, apply the receiving-review decision tree: VERIFY accuracy (cite actual code if inaccurate), then HARM CHECK (breaks functionality / conflicts with documented design decision). If none apply: FIX IT. If harm found: PUSH BACK with cited evidence.
      4. Apply fixes inline to the affected card file(s). If a fix changes shared context (e.g. Card Index in 00-overview.md), update 00-overview.md too. Check systemic implications — a fix in one card may require updates to other cards.
      5. Write ONE consolidated fixer report `_millhouse/task/reviews/<timestamp>-plan-fix-r<N>.md` with `## Fixed` and `## Pushed Back` sections. The `## Pushed Back` section must have a `### <slice-id>` subsection for every slice reviewed this round:
         ```markdown
         ## Pushed Back
         ### card-1
         - Finding X: description (or "(empty — slice approved this round)")
         ### holistic
         (empty — slice approved this round)
         ```
      6. Call `outcome = loop.record_round_result(verdicts, fixer_report_path)` and route: `"CONTINUE"` → step 2l; `"BLOCKED_NON_PROGRESS"` → step 2i; `"BLOCKED_MAX_ROUNDS"` → step 2j.

   i. **On `outcome == "BLOCKED_NON_PROGRESS"`:** Update status.md with `blocked: true`, `blocked_reason: Plan review non-progress — identical pushed-back findings in consecutive rounds`, `phase: blocked`. Insert `blocked  <timestamp>` in the timeline. Run the **Notification Procedure** with `BLOCKED: Plan review non-progress after consecutive rounds`. Escalate to user immediately.

   j. **On `outcome == "BLOCKED_MAX_ROUNDS"`:** Update status.md with `blocked: true`, `blocked_reason: Plan review dispute after <max_plan_review_rounds> rounds`, `phase: blocked`. Insert `blocked  <timestamp>` in the timeline. Run the **Notification Procedure** with `BLOCKED: Plan review dispute after <max_plan_review_rounds> rounds`. Present remaining BLOCKING issues to user.

   k. Insert `plan-review-r<N>  <timestamp>` and `plan-fix-r<N>  <timestamp>` lines in the timeline text block.

   l. Re-spawn **all N+1 reviewers** (all per-card slices + holistic) with the updated plan directory. Do not carry forward prior-round approvals — stale approvals are not trusted (a fix in one card can invalidate the holistic reviewer's prior approval). Report: **"Plan Review — round N/&lt;max_plan_review_rounds&gt;"**

### Phase: Handoff

3. Update the YAML code block in `_millhouse/task/status.md`:
   - Update `phase:` to `planned`.
   - Ensure `plan: _millhouse/task/plan` is present as a field.
   - Preserve `task:`, `task_description:`, `discussion:`, `parent:`, and `plan_start_hash:` fields.

   Insert `planned  <timestamp>` before the closing ` ``` ` of the timeline text block. Generate timestamp via shell: `date -u +"%Y-%m-%dT%H:%M:%SZ"`.

4. Report:
   > Plan written and approved. Run `mill-go` to start the Builder.

---

## Stops When

mill-plan stops in any of these situations:

- **Plan reviewer blocks** after `max_plan_review_rounds` rounds → block, notify, stop
- **Non-progress detected** — identical pushed-back findings in consecutive rounds → block, notify, stop

---

## Board Updates

Phase transitions are tracked via `phase:` in the YAML code block of `_millhouse/task/status.md` and the `## Timeline` section (entries inserted before the closing ` ``` ` of the text fence). See `plugins/mill/doc/formats/discussion.md` for the status.md schema and timeline format.

mill-plan does not write to the parent's `tasks.md`. The `[active]` marker written by `mill-start` / `mill-spawn` (via `spawn_task.py`) remains until `mill-merge` (`[done]`) or `mill-abandon` (`[abandoned]`).

---

## Notification Procedure

When the skill says "notify user", follow this procedure. Notifications are NOT a separate skill — they are inline calls made at specific points in mill-plan.

### Step 1: Update status file (always)

Write the event to the YAML code block in `_millhouse/task/status.md`. For blocking events, ensure `blocked: true` and `blocked_reason:` are set.

### Step 2: Send notification

Run the `notify` Python entrypoint. Best-effort — failures warn on stderr, never block execution.

```bash
(cd plugins/mill/scripts && python -m millpy.entrypoints.notify) \
  --event "<EVENT>" \
  --branch "$(git branch --show-current)" \
  --detail "<detail>" \
  --urgency "<info|high>"
```

### When to notify (mill-plan)

| Call site | Event | Urgency |
|-----------|-------|---------|
| Phase: Plan Review — non-progress after consecutive fixer rounds | `BLOCKED: Plan review non-progress` | High |
| Phase: Plan Review — dispute after max rounds | `BLOCKED: Plan review dispute` | High |

---

## Post-Failure State

On any failure that blocks progress:

1. Update the YAML code block in `_millhouse/task/status.md` with `blocked: true`, `blocked_reason:`, and `phase: blocked`. Use the Edit tool to insert `blocked  <timestamp>` before the closing ` ``` ` of the timeline text block.
2. Preserve all state — do not clean up, do not rollback automatically.
3. Run the **Notification Procedure** with the BLOCKED event.
4. Report the blocker to the user.
