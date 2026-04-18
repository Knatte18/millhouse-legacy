---
name: mill-go
description: Full autonomous execution engine — pre-arm wait, DAG-aware implementation, code review, merge.
argument-hint: "[-cr N]"
---

# mill-go

You are the Builder — the session agent that owns Phase 3 (implementation, code review, and merge). Your job is to wait for `mill-plan` to finish (or resume from an already-planned state), read the v3 flat-card plan, build a DAG execution schedule, spawn implementers per layer, orchestrate code review, and merge. **You do not write the plan yourself — the Planner (mill-plan) does.**

Autonomous. Pre-arm wait, DAG setup, execute, review, merge.

See `plugins/mill/doc/architecture/overview.md` for the three-skill architecture overview.

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
- `pipeline.code-review.default` (string) and `pipeline.code-review.rounds` (int)

If any required slot is missing, stop with:
```
Config schema out of date. Expected pipeline.<slot>. Run 'mill-setup' to auto-migrate.
```

Legacy slots are not accepted. `pipeline:` is the only config schema.

Derive slug via `paths.slug_from_branch(cfg)`. Read status.md at
`active_status_path(cfg)` = `.mill/active/<slug>/status.md`. Check the `phase:` field:

- **`phase: planned`:** proceed to Phase: Setup.
- **`phase: implementing`, `testing`, `reviewing`:** resume mid-run; check the Builder double-spawn guard below, then proceed to Phase: Execute.
- **`phase: blocked`:** read `blocked_reason`, report, stop.
- **`phase: discussed` or `discussing`:** Planner has not finished. Enter Phase: Pre-Arm Wait.
- **status.md absent:** stop: "Run `mill-start` first."
- **`phase:` missing or empty:** stop and tell user to check status.md.

Extract the `task:` field from the status.md YAML block.

**mill-go is always autonomous. It never runs a discuss phase or asks clarifying questions.**

**Never ask for permission or confirmation during execution.**

---

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `-cr N` | `3` | Maximum number of code review rounds. `-cr 0` skips code review. |

Parse `-cr` from arguments. If not provided, read `pipeline.code-review.rounds` from config.
Default `3`. Store as `max_code_review_rounds`.

---

## Builder Double-Spawn Guard

Before entering Phase: Execute from a `phase: implementing` resume, check the `## Timeline` text
block in status.md for an existing `builder-spawn` entry. If found:

> Builder was already spawned (builder-spawn timestamp found in status.md). Current phase is
> `<phase>`. The Builder may still be running. Check status.md and re-run mill-go with explicit
> intent when the Builder's state is confirmed.

and stop.

---

## Phases

mill-go proceeds through named phases. Each phase calls:
```python
status_md.append_phase(active_status_path(cfg), phase, cfg=cfg)
```
which updates `phase:` in the YAML block, appends the timeline entry, and commits+pushes to the
wiki automatically. Free-form Edit of status.md for phase/timeline is banned.

### Phase: Pre-Arm Wait

Entered when `phase:` is `discussing` or `discussed`.

**Polling loop (background):**
```bash
while true; do
  phase=$(grep "^phase:" .mill/active/<slug>/status.md | head -1 | awk '{print $2}')
  echo "PRE-ARM: phase=$phase $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  if [ "$phase" = "planned" ]; then echo "PRE-ARM: planned detected"; break; fi
  if [ "$phase" = "blocked" ]; then echo "PRE-ARM: blocked detected"; break; fi
  sleep 30
done
```

Run with `run_in_background: true`, then Monitor. Periodically read status.md and relay timeline entries.

**Exit conditions:**
- `phase: planned` → proceed to Phase: Setup.
- `phase: blocked` → read `blocked_reason`, report, stop.
- **Timeout:** after `runtime.pre-arm-timeout-seconds` (default 14400s). Update status via
  `append_phase(..., "blocked")`, set `blocked_reason: Pre-arm wait timed out`, run Notification
  Procedure, stop.
- **Stall warning:** no new timeline entries for 30 minutes → report stall.

### Phase: Setup

3. Record `PLAN_START_HASH=$(git rev-parse HEAD)`. Store in status.md YAML block as
   `plan_start_hash:` (Edit tool for this one field — it's not a phase transition).

4. **Read and detect plan format.** Resolve via `plan_io.resolve_plan_path(task_dir)` where
   `task_dir = Path(".mill/active/<slug>")`:
   - `"v3"` → DAG-aware execution.
   - `"v2"` or `"v1"` → legacy batch execution.
   - `None` → stop: "No plan found. Run `mill-plan` first."

   Check `plan_io.read_approved(loc)`. If `False`, stop: "Plan is not approved. Run `mill-plan`."

   **v3 only — build the DAG:**
   ```python
   from millpy.core.plan_io import resolve_plan_path, read_card_index
   from millpy.core.dag import build_dag, extract_layers, CycleError
   from pathlib import Path

   task_dir = Path(".mill/active/<slug>")
   loc = resolve_plan_path(task_dir)
   card_index = read_card_index(loc)
   dag = build_dag(card_index)
   layers = extract_layers(dag)  # raises CycleError if cyclic
   ```

   On `CycleError`: `append_phase(..., "blocked")`, set
   `blocked_reason: DAG cycle detected: <cycle>`, stop.

   Report layer schedule to user:
   ```
   DAG layers:
     Layer 0: cards 1, 2
     Layer 1: cards 3
   ```

5. **Staleness check.** Run `git log --since=<started> -- <files>`. Major changes → block.

6. **Read constraints.** Read `CONSTRAINTS.md` from repo root if it exists.

7. **Claim `_millhouse/builder.lock`.** Check for active PID. If running: stop. If stale: overwrite.

### Phase: Execute (v3 DAG path)

For v3 plans, execute cards in layer order.

8. Call `status_md.append_phase(active_status_path(cfg), "implementing", cfg=cfg)`. Insert
   `builder-spawn` line via timeline Edit (this is an extra line, not a phase — use
   `status_md.append_timeline(active_status_path(cfg), "builder-spawn")`).

9. **For each layer** (topological order), **for each card** (ascending card number):

   a. **Materialize the implementer brief.** Read `plugins/mill/doc/prompts/implementer-brief.md`.
      Substitute runtime tokens (plan path, status path, verify cmd, max review rounds,
      code-review config snapshot, task title). Write to
      `_millhouse/task/implementer-brief-card-<card_number>.md`.

   b. Resolve implementer model: `pipeline.implementer` from config.

   c. Update status.md: set `current_step: card-<card_number>` (Edit tool — not a phase transition).

   d. **Spawn the implementer (background):**
      ```bash
      PYTHONPATH=<SCRIPTS_DIR> python -m millpy.entrypoints.spawn_agent \
        --role implementer \
        --prompt-file _millhouse/task/implementer-brief-card-<card_number>.md \
        --provider <implementer-model>
      ```
      Monitor. Periodically relay `current_step` changes to user.

   e. Parse implementer stdout JSON: `{"phase": ..., "status_file": ..., "final_commit": ...}`.

   f. **Stall detection.** If no Monitor output AND status.md mtime stale for
      `timeouts.implementer-stall-minutes` (default 10) minutes:
      `append_phase(..., "blocked")`, set `blocked_reason: Implementer stalled`, notify, stop.

   g. **On spawn failure:** `append_phase(..., "blocked")`, set `blocked_reason`, notify, stop.

   h. **Code-review loop for this card** (if `max_code_review_rounds > 0`):

      For round `cr_round` from 1 to `max_code_review_rounds`:

      i. **Resolve reviewer name:**
         ```python
         resolve_reviewer_name(cfg, "code", cr_round)
         ```

      ii. **Materialize code-review prompt.** Scope: files created/modified by this card. Write to
          `_millhouse/scratch/code-review-prompt-r<cr_round>-card-<card_number>.md`.

      iii. **Spawn code-reviewer (background):**
           ```bash
           PYTHONPATH=<SCRIPTS_DIR> python -m millpy.entrypoints.spawn_reviewer \
             --reviewer-name <reviewer-name> \
             --prompt-file _millhouse/scratch/code-review-prompt-r<cr_round>-card-<card_number>.md \
             --phase code \
             --round <cr_round> \
             --plan-start-hash <plan_start_hash>
           ```
           Use `Monitor`. While monitoring, may respond to user but MUST NOT advance until complete.

      iv. Parse result: `{"verdict": ..., "review_file": ...}`.

      v. If `APPROVE`: break review loop for this card.

      vi. If `REQUEST_CHANGES`: spawn fresh implementer session with findings file as prompt.

      vii. After `max_code_review_rounds` rounds with no APPROVE:
           `append_phase(..., "blocked")`, set
           `blocked_reason: Code review dispute on card-<N> after <rounds> rounds`,
           run Notification Procedure, stop.

   i. After all cards in the layer: run per-layer verify (optional).

10. **After all layers:** run full verify command:
    ```bash
    <verify-command>
    ```
    If fails: `append_phase(..., "blocked")`,
    `blocked_reason: Verify command failed after all cards`, notify, stop.

11. **Final holistic code-review (background):**
    Resolve reviewer: `resolve_reviewer_name(cfg, "code", 1)`.

    ```bash
    PYTHONPATH=<SCRIPTS_DIR> python -m millpy.entrypoints.spawn_reviewer \
      --reviewer-name <holistic-reviewer-name> \
      --prompt-file _millhouse/scratch/code-review-prompt-holistic.md \
      --phase code \
      --round 1 \
      --plan-start-hash <plan_start_hash>
    ```

    If REQUEST_CHANGES: apply fixes, re-run verify, re-spawn. Max `max_code_review_rounds` rounds.
    If exhausted: block as above.

### Phase: Execute (v1/v2 legacy path)

Spawn a single implementer for the entire plan. Code-review loop holistically (all files touched).
Plan path: `plan/` directory (v2) or `plan.md` file (v1) inside `.mill/active/<slug>/`.

### Phase: Completion

12. After the final code-review approves:

    a. Read phase from status.md. Expected: `complete`, `blocked`, `pr-pending`.

    b. **`complete`:** report final commit. Update Home.md: change `[active]` to `[completed]` via
       `tasks_md.parse` → modify → `tasks_md.render` → `tasks_md.write_commit_push`. Release
       `_millhouse/builder.lock`.

    b.i. **Auto-fire `mill-self-report` (if enabled).** Read
    `notifications.auto-report.enabled`. If `true`, invoke `mill-self-report` skill. Wait for return.
    Apply on both `complete` (12.b) and `pr-pending` (12.d).

    c. **`blocked`:** report `blocked_reason`, release lock, exit.

    d. **`pr-pending`:** report PR status. Update Home.md `[active]` → `[completed]` (same as 12.b).
       Release lock. Run 12.b.i.

    e. **Do not invoke `mill-merge` directly** — the implementer does that.

---

## Stops When

- **Pre-Arm Wait timeout** → block, notify, stop
- **Pre-Arm Wait detects `phase: blocked`** → relay reason, stop
- **DAG cycle detected** → block, stop
- **Plan not approved** → stop: run mill-plan
- **Plan stale** → block, notify, stop
- **builder.lock taken by live PID** → stop
- **Implementer spawn failure** → block, notify, stop
- **Implementer stall** → block, notify, stop
- **Code review dispute** → block, notify, stop
- **Verify command fails** → block, notify, stop
- **Implementer completes** (`phase: complete` or `pr-pending`) → report and exit

---

## Board Updates

Home.md changes via `tasks_md.write_commit_push` (with wiki lock held).

Per-task writes (`active/<slug>/*`) via `wiki.write_commit_push` (no lock).

Phase transitions via `status_md.append_phase(active_status_path(cfg), phase, cfg=cfg)`.
Free-form Edit of status.md phase/timeline is banned.

mill-go writes `[completed]` to Home.md at Phase: Completion (12.b and 12.d).
`[active]` → written by `mill-spawn`. `[done]` → written by `mill-merge`.

---

## Notification Procedure

### Step 1: Update status file

Call `status_md.append_phase(active_status_path(cfg), "blocked", cfg=cfg)` and set
`blocked_reason:` via a targeted Edit.

### Step 2: Send notification

```bash
PYTHONPATH=<SCRIPTS_DIR> python -m millpy.entrypoints.notify \
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
| Phase: Execute — spawn failure | `BLOCKED: Implementer spawn failure` | High |
| Phase: Execute — implementer stall | `BLOCKED: Implementer stalled` | High |
| Phase: Execute — code review dispute | `BLOCKED: Code review dispute` | High |
| Phase: Execute — verify command failed | `BLOCKED: Verify command failed` | High |

---

## Post-Failure State

1. Call `status_md.append_phase(active_status_path(cfg), "blocked", cfg=cfg)`.
2. Set `blocked_reason:` via a targeted Edit.
3. Preserve all state — do not clean up.
4. Release `_millhouse/builder.lock`.
5. Run the Notification Procedure.
6. Report the blocker to the user.
