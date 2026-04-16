---
name: mill-go
description: Full autonomous execution engine — pre-arm wait, DAG-aware implementation, code review, merge.
argument-hint: "[-cr N]"
---

# mill-go

You are the Builder — the session agent that owns Phase 3 (implementation, code review, and merge). Your job is to wait for `mill-plan` to finish (or resume from an already-planned state), read the v3 flat-card plan, build a DAG execution schedule, spawn Sonnet implementers per card/layer, orchestrate code review, and merge. **You do not write the plan yourself — the Planner (mill-plan) does.**

Autonomous. Pre-arm wait, DAG setup, execute, review, merge.

See `plugins/mill/doc/architecture/overview.md` for the three-skill architecture overview. This skill is the runtime spec for Phase 3 (Builder execution).

---

## Entry

Read `_millhouse/config.yaml`. If it does not exist, stop — tell the user to run `mill-setup` first.

**Entry-time validation.** Validate `_millhouse/config.yaml`. Required slots under the `pipeline:` block:
- `pipeline.implementer` (string) — the subagent model for `millpy.entrypoints.spawn_agent` dispatch
- `pipeline.code-review.default` (string) and `pipeline.code-review.rounds` (int)

(`pipeline.plan-review.*` is required by `mill-plan`, not by `mill-go`; the Builder only runs code review.)

If any required slot is missing, stop with:
```
Config schema out of date. Expected pipeline.<slot>. Run 'mill-setup' to auto-migrate.
```

Legacy slots (`models.session`, `models.explore`, `models.<phase>-review`, `review-modules:`, `reviews:`) are not accepted. The `pipeline:` block is the only config schema.

Read `_millhouse/task/status.md`. Check the `phase:` field:

- **`phase: planned`:** proceed directly to Phase: Setup.
- **`phase: implementing`, `testing`, `reviewing`:** resume mid-run; check the Builder double-spawn guard below, then proceed to Phase: Execute at the current step.
- **`phase: blocked`:** read `blocked_reason`, report, stop.
- **`phase: discussed` or `discussing`:** the Planner has not finished. Enter Phase: Pre-Arm Wait.
- **`status.md` absent:** stop with "Run `mill-start` first."
- **`phase:` missing or empty:** stop and tell the user to check `_millhouse/task/status.md`.

Extract the `task:` field from the YAML code block in status.md to identify the task title.

**mill-go is always autonomous. It never runs a discuss phase or asks clarifying questions. That is `mill-start`'s job.**

**Never ask for permission or confirmation during execution.** The only valid stopping points are listed in "Stops When" below.

---

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `-cr N` | `3` | Maximum number of code review rounds per card. `-cr 0` skips code review entirely. |

Parse `-cr` from the skill invocation arguments. If not provided via CLI, read `pipeline.code-review.rounds` from `_millhouse/config.yaml`. CLI arg overrides config. Default `3`. Store as `max_code_review_rounds`.

---

## Builder Double-Spawn Guard

Before entering Phase: Execute from a `phase: implementing` resume, check the `## Timeline` text block in `_millhouse/task/status.md` for an existing `builder-spawn` entry. If found: a prior spawn occurred in this session. Do **not** re-spawn — instead report:

> Builder was already spawned (builder-spawn timestamp found in status.md). Current phase is `<phase>`. The Builder may still be running or may have exited. Check `_millhouse/task/status.md` for current state and re-run mill-go with explicit intent when the Builder's state is confirmed.

and stop.

---

## Phases

mill-go proceeds through named phases. Each phase updates the YAML code block in `_millhouse/task/status.md` with the current phase name and relevant fields, and inserts timeline entries before the closing ` ``` ` of the timeline text block.

### Phase: Pre-Arm Wait

Entered when `phase:` is `discussing` or `discussed` (the Planner has not yet set `phase: planned`).

**On entry:**
- If `_millhouse/task/status.md` is absent → stop: "Run `mill-start` first."
- If `phase: blocked` → read `blocked_reason`, report, stop.
- If `phase: discussing` or `phase: discussed` → enter the polling loop below.

**Polling loop:**

Implement as a bash `while` loop with `sleep 30`, run with `run_in_background: true`, then Monitor the shell:

```bash
while true; do
  phase=$(grep "^phase:" _millhouse/task/status.md | head -1 | awk '{print $2}')
  echo "PRE-ARM: phase=$phase $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  if [ "$phase" = "planned" ]; then
    echo "PRE-ARM: planned detected"
    break
  fi
  if [ "$phase" = "blocked" ]; then
    echo "PRE-ARM: blocked detected"
    break
  fi
  sleep 30
done
```

Read `_millhouse/task/status.md` on each Monitor event to verify phase. Read and display recent `## Timeline` entries to show Planner progress.

**Exit conditions:**
- `phase: planned` → proceed to Phase: Setup.
- `phase: blocked` → read `blocked_reason`, report, stop.
- **Timeout:** track elapsed time via a counter (polls × 30 seconds). Timeout after `runtime.pre-arm-timeout-seconds` from `_millhouse/config.yaml` (default 14400 seconds / 4 hours). On timeout: update status.md `phase: blocked`, `blocked_reason: Pre-arm wait timed out after <N> seconds`, insert `blocked <timestamp>` in timeline, run Notification Procedure, stop.
- **Stall warning:** if the `## Timeline` text block has not gained new entries for 30 minutes of polling (60 × 30s iterations), report: "No Planner timeline activity in 30 minutes. The Planner may be stalled. Waiting..."

### Phase: Setup

3. Record `PLAN_START_HASH=$(git rev-parse HEAD)`. Store in the YAML code block of `_millhouse/task/status.md` as `plan_start_hash:`. On resume, read from the YAML code block in status.md instead of re-computing.

4. **Read and detect the plan format.** Resolve the plan via `plan_io.resolve_plan_path(task_dir)` (where `task_dir = _millhouse/task/`). Check `loc.kind`:
   - `"v3"` → use DAG-aware execution (Phase: Execute below).
   - `"v2"` → use legacy batch execution (Phase: Execute legacy path below).
   - `"v1"` → use legacy single-file execution (Phase: Execute legacy path below).
   - `None` → stop: "No plan found. Run `mill-plan` first."

   Check `plan_io.read_approved(loc)`. If `False`, stop: "Plan is not approved. Run `mill-plan` to complete plan review."

   Read `plan_io.read_files_touched(loc)`, `plan_io.read_verify(loc)`, `plan_io.read_dev_server(loc)`, `plan_io.read_started(loc)`.

   **v3 only — build the DAG:**

   ```python
   from millpy.core.plan_io import resolve_plan_path, read_card_index
   from millpy.core.dag import build_dag, extract_layers, CycleError
   from pathlib import Path

   task_dir = Path("_millhouse/task")
   loc = resolve_plan_path(task_dir)
   card_index = read_card_index(loc)
   dag = build_dag(card_index)
   try:
       layers = extract_layers(dag)
   except CycleError as e:
       # stop — report cycle
   ```

   On `CycleError`: update status.md `phase: blocked`, `blocked_reason: DAG cycle detected in card dependency graph: <cycle>`. Stop.

   Report the layer schedule to the user:
   ```
   DAG layers:
     Layer 0: cards 1, 2
     Layer 1: cards 3
     Layer 2: cards 4, 5, 6
   ```

5. **Staleness check.** Run `git log --since=<started> -- <file1> <file2> ...` using the `started:` timestamp from `plan_io.read_started(loc)` and files from `plan_io.read_files_touched(loc)`.
   - No changes: proceed.
   - Minor changes (formatting, comments, unrelated areas): log warning in status.md, proceed.
   - Major changes (files restructured, APIs changed, interfaces modified): halt. Plan-stale revert:
     1. Update the YAML code block in `_millhouse/task/status.md` with `blocked: true`, `blocked_reason: Plan stale — files changed since plan was written`, `phase: blocked`. Insert `blocked  <timestamp>` in the timeline. Run the **Notification Procedure** with `BLOCKED: Plan stale — files changed`. Tell the user to re-run `mill-start`.

6. **Read constraints.** Resolve repo root: `git rev-parse --show-toplevel`. Read `CONSTRAINTS.md` from repo root if it exists.

7. **Claim `builder.lock`.** Check for `_millhouse/builder.lock`. If present, read the PID and check if it is still running (`ps -p <PID>` or Windows equivalent). If running: stop — "Another Builder is active (PID <PID>). If stale, delete `_millhouse/builder.lock` and retry." If stale: overwrite. Write `_millhouse/builder.lock` with the current PID and timestamp.

### Phase: Execute (v3 DAG path)

For v3 plans, execute cards in layer order using the DAG built in Phase: Setup.

8. Update status.md: `phase: implementing`. Insert `implementing  <timestamp>` and `builder-spawn  <timestamp>` in the timeline. The `builder-spawn` line is the double-spawn-guard signal.

9. **For each layer** (in topological order, Layer 0 first):

   For each card in the layer (in ascending card-number order):

   a. **Materialize the implementer brief.** Read the brief template from `plugins/mill/doc/prompts/implementer-brief.md`. Substitute the runtime tokens:
      - `<PLAN_PATH>` → absolute path to the card file (e.g. `_millhouse/task/plan/card-NN-<slug>.md`)
      - `<STATUS_PATH>` → absolute path to `_millhouse/task/status.md`
      - `<WORK_DIR>` → output of `git rev-parse --show-toplevel`
      - `<REPO_ROOT>` → same as `<WORK_DIR>`
      - `<VERIFY_CMD>` → from `plan_io.read_verify(loc)`
      - `<MAX_CODE_REVIEW_ROUNDS>` → resolved `max_code_review_rounds`
      - `<CODE_REVIEW_RESOLUTION_SNAPSHOT>` → the `pipeline.code-review` block from `_millhouse/config.yaml`, verbatim
      - `<TASK_TITLE>` → task title from status.md

      Write to `_millhouse/task/implementer-brief-card-<card_number>.md`.

   b. **Resolve the implementer model.** Read `pipeline.implementer` from `_millhouse/config.yaml`.

   c. **Update status.md** `current_step: card-<card_number>`.

   d. **Spawn the implementer.** Invoke with `run_in_background: true`:
      ```bash
      (cd plugins/mill/scripts && python -m millpy.entrypoints.spawn_agent) \
        --role implementer \
        --prompt-file _millhouse/task/implementer-brief-card-<card_number>.md \
        --provider <implementer-model>
      ```
      Monitor the shell ID. While monitoring, periodically read `_millhouse/task/status.md` and relay each `current_step` change to the user.

   e. **Capture session-ID from output JSON.** Parse the implementer's stdout JSON line: `{"phase": ..., "status_file": ..., "final_commit": ..., "session_id": ...}`. Store `session_id` (may be `null` — the Claude CLI does not expose it in JSON output, so session resume is a no-op for now; the slot exists for future use).

   f. **Stall detection.** If Monitor produces no output AND status.md mtime has not advanced for `timeouts.implementer-stall-minutes` (default 10) minutes, report stall and stop. Update status.md `phase: blocked`, `blocked_reason: Implementer stalled on card-<card_number>`. Run Notification Procedure. Stop.

   g. **On implementer exit (non-zero before phase: implementing was written):** update status.md `phase: blocked`, `blocked_reason: Implementer spawn failure on card-<card_number>: <stderr>`. Run Notification Procedure. Stop.

   h. **Code-review loop for this card** (if `max_code_review_rounds > 0`):

      For round `cr_round` from 1 to `max_code_review_rounds`:

      i. **Resolve the code-reviewer name.** Prefer `pipeline.code-review.<cr_round>` from config; if absent, fall back to `pipeline.code-review.default`. Use `resolve_reviewer_name(cfg, "code", cr_round)`.

      ii. **Materialize the code-review prompt.** Identify review scope: the files created/modified by this card (from `card_index[card_number]["creates"] + card_index[card_number]["modifies"]`, root-resolved). Write prompt to `_millhouse/scratch/code-review-prompt-r<cr_round>-card-<card_number>.md`.

      iii. **Spawn code-reviewer:**
           ```bash
           (cd plugins/mill/scripts && python -m millpy.entrypoints.spawn_reviewer) \
             --reviewer-name <code-reviewer-name> \
             --prompt-file _millhouse/scratch/code-review-prompt-r<cr_round>-card-<card_number>.md \
             --phase code \
             --round <cr_round> \
             --slice-type per-card \
             --slice-id card-<card_number>
           ```

      iv. **Parse result:** `{"verdict": ..., "review_file": ...}`.

      v. If `APPROVE`: break the code-review loop for this card.

      vi. If `REQUEST_CHANGES`: send findings to the implementer for fixes.

          **Session resume attempt:** if `session_id` is non-null, use `spawn_agent.py --session-id <session_id>` with the findings file as prompt. If `session_id` is null (normal for current CLI), spawn a **fresh Sonnet session** with the findings file as the prompt:
          ```bash
          (cd plugins/mill/scripts && python -m millpy.entrypoints.spawn_agent) \
            --role implementer \
            --prompt-file <findings-path> \
            --provider <implementer-model>
          ```
          The fresh session prompt must include: the findings file path, the card file path, and instruction to apply fixes to the identified files.

          **`[autonomous-fix]` policy:** if the Builder encounters a tool failure during this card's execution and applies an out-of-plan fix, commit with prefix `[autonomous-fix]`. Max 1 autonomous fix per run. Record the SHA in the final JSON output.

      vii. After `max_code_review_rounds` rounds with no APPROVE: update status.md `phase: blocked`, `blocked_reason: Code review dispute on card-<card_number> after <N> rounds`. Insert `blocked  <timestamp>` in timeline. Run Notification Procedure. Stop.

   i. **After all cards in the layer complete:** run per-layer tests (optional, run `<VERIFY_CMD>` scoped to the layer's output files if possible).

10. **After all layers:** run full `<VERIFY_CMD>`:
    ```bash
    <verify-command>
    ```
    If verify fails, update status.md `phase: blocked`, `blocked_reason: Verify command failed after all cards implemented`. Run Notification Procedure. Stop.

11. **Final holistic code-review.** After verify passes, spawn a final holistic code-review:

    Resolve reviewer: `resolve_reviewer_name(cfg, "code", 1)` (or a dedicated holistic reviewer if `pipeline.code-review.holistic` is set).

    ```bash
    (cd plugins/mill/scripts && python -m millpy.entrypoints.spawn_reviewer) \
      --reviewer-name <holistic-reviewer-name> \
      --prompt-file _millhouse/scratch/code-review-prompt-holistic.md \
      --phase code \
      --round 1 \
      --slice-type holistic \
      --slice-id holistic
    ```

    If REQUEST_CHANGES: apply fixes, re-run verify, re-spawn holistic reviewer. Max `max_code_review_rounds` rounds. If exhausted: block as above.

### Phase: Execute (v1/v2 legacy path)

For v1 and v2 plans, materialize the implementer brief using the full plan (not individual cards):

- `<PLAN_PATH>` → the full plan location (`_millhouse/task/plan` directory for v2, `_millhouse/task/plan.md` file for v1).
- Spawn a single Sonnet implementer for the entire plan.
- After completion, run the code-review loop holistically (single scope = all files touched).
- The rest of the lifecycle mirrors the v3 path above.

### Phase: Completion

12. After the final code-review approves:

    a. Read `_millhouse/task/status.md` `phase:`. Expected: `complete`, `blocked`, `pr-pending`.

    b. **`complete`:** report:
       > Task complete. Final commit: `<final_commit>`. Phase: complete.

       Release `_millhouse/builder.lock`. Notification was already sent by the final implementer session or mill-merge.

    c. **`blocked`:** report `blocked_reason` from status.md, release lock, exit.

    d. **`pr-pending`:** report:
       > Task complete; PR pending. Run `gh pr view` for details.

       Release lock. Notification was already sent by mill-merge.

    e. The Builder's responsibilities end here. **Do not invoke `mill-merge` directly** — the implementer does that.

---

## Stops When

mill-go (Builder) stops in any of these situations:

- **Pre-Arm Wait timeout** → block, notify, stop
- **Pre-Arm Wait detects `phase: blocked`** → relay reason, stop
- **DAG cycle detected** → block, stop
- **Plan not approved** (`approved: false`) → stop: run mill-plan
- **Plan stale** (major changes to listed files) → block, notify, stop
- **builder.lock taken by live PID** → stop: another Builder is active
- **Implementer spawn failure** → block, notify, stop
- **Implementer stall** (no Monitor output AND status.md mtime stale for N minutes) → block, notify, stop
- **Code review dispute** (max rounds exhausted per card or holistically) → block, notify, stop
- **Verify command fails** → block, notify, stop
- **Implementer completes** (`phase: complete` or `pr-pending`) → report final state and exit

---

## Board Updates

tasks.md changes require commit and push (tasks.md is git-tracked). When running from a child worktree, resolve the parent's project root by computing the project subdirectory offset and applying it to the parent worktree path from `git worktree list --porcelain`.

Phase transitions are tracked via `phase:` in the YAML code block of `_millhouse/task/status.md` and the `## Timeline` section. See `plugins/mill/doc/formats/discussion.md` for the status.md schema.

mill-go (Builder) does not write to the parent's `tasks.md`. The `[active]` marker written at claim time by `mill-start` / `mill-spawn` (via `spawn_task.py`) remains in place. `mill-merge` writes `[done]` on successful merge; `mill-abandon` writes `[abandoned]` on abandonment.

**Plan stale:** mill-go updates `_millhouse/task/status.md` with `blocked: true` but does NOT remove the `[active]` marker.

---

## Notification Procedure

When the skill says "notify user", follow this procedure.

### Step 1: Update status file (always)

Write the event to the YAML code block in `_millhouse/task/status.md`. For blocking events, ensure `blocked: true` and `blocked_reason:` are set.

### Step 2: Send notification

```bash
(cd plugins/mill/scripts && python -m millpy.entrypoints.notify) \
  --event "<EVENT>" \
  --branch "$(git branch --show-current)" \
  --detail "<detail>" \
  --urgency "<info|high>"
```

### When to notify (mill-go / Builder)

| Call site | Event | Urgency |
|-----------|-------|---------|
| Phase: Pre-Arm Wait — timeout | `BLOCKED: Pre-arm wait timed out` | High |
| Phase: Setup — plan stale | `BLOCKED: Plan stale — files changed` | High |
| Phase: Execute — implementer spawn failure | `BLOCKED: Implementer spawn failure` | High |
| Phase: Execute — implementer stall | `BLOCKED: Implementer stalled` | High |
| Phase: Execute — code review dispute | `BLOCKED: Code review dispute` | High |
| Phase: Execute — verify command failed | `BLOCKED: Verify command failed` | High |

The Planner's own call sites (plan-review escalation) are handled by `mill-plan`. The implementer's call sites (test failure, merge, completion) live in `implementer-brief.md`. mill-go relays the blocked state and exits.

---

## Systematic Debugging Protocol

The Systematic Debugging Protocol applies during implementer execution. See `plugins/mill/doc/prompts/implementer-brief.md` `### 9. Systematic Debugging Protocol` for the full protocol. The Builder does not debug code — it only spawns and reports.

---

## Post-Failure State

On any Builder failure that blocks progress:

1. Update the YAML code block in `_millhouse/task/status.md` with `blocked: true`, `blocked_reason:`, and `phase: blocked`. Use the Edit tool to insert `blocked  <timestamp>` before the closing ` ``` ` of the timeline text block.
2. Preserve all state — do not clean up, do not rollback automatically.
3. Release `_millhouse/builder.lock`.
4. Run the **Notification Procedure** with the BLOCKED event.
5. Report the blocker to the user.
