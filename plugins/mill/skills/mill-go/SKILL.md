---
name: mill-go
description: Full autonomous execution engine — plan, implement, review, merge.
argument-hint: "[-pr N] [-cr N]"
---

# mill-go

You are Thread A — the session agent that owns Phase 2 (plan writing + plan review). Your job is to write the implementation plan from the discussion file, submit it for review, then spawn Thread B (the implementer-orchestrator) to handle implementation, code review, and merge. **You do not implement the plan yourself — Thread B does.** You block until Thread B completes and report its result to the user.

Autonomous. Plan, review, spawn Thread B, report.

See `plugins/mill/doc/overview.md` for the two-thread architecture overview, the four-phase flow, and the spawn mechanism. This skill is the runtime spec for Phase 2 + Thread B spawn.

---

## Entry

Read `_millhouse/config.yaml`. If it does not exist, stop --- tell the user to run `mill-setup` first.

**Entry-time validation.** Validate `_millhouse/config.yaml` per `plugins/mill/doc/modules/validation.md`. Required slots: `models.session` (string), `models.implementer` (string), `models.explore` (string). For review phases, accept either the new `review-modules.<phase>.default` OR the legacy `models.<phase>-review.default` — prefer the new one if present. If neither is present for any phase, stop with:
```
Config schema out of date. Expected review-modules.<phase>.default (string). Run 'mill-setup' to auto-migrate.
```

For legacy configs (no `review-modules:` block), validate the legacy slots: `models.discussion-review.default`, `models.plan-review.default`, `models.code-review.default`. On failure, stop with the exact error message:

```
Config schema out of date. Expected models.<slot> (<type>). Run 'mill-setup' to auto-migrate.
```

Do not attempt auto-migration here — that is `mill-setup`'s job. See `plugins/mill/doc/overview.md#config-migration`.

Read `_millhouse/task/status.md`. Check the `phase:` field from the YAML code block is exactly `discussed` (the completion sentinel confirming `mill-start` finished normally) **or** `planned` (Pre-Setup resume). If `phase:` is missing, not one of those two, or is a partial value (e.g. `discussing`), check the resume rules below.

**Phase past `planned` on entry.** If `phase:` is `implementing`, `testing`, `reviewing`, or `blocked`, mill-go does not re-enter Thread B's domain. Report the current state from status.md and stop. Re-spawning Thread B is a manual step the user takes by re-running mill-go with explicit intent (e.g. after they verify Thread B is no longer running and they want to retry).

Extract the `discussion:` field from the YAML code block to locate the discussion file. Read it. If it does not exist, stop --- tell the user to re-run `mill-start`.

Read the discussion file frontmatter. Validate the `worktree:` field matches the current working directory (`git rev-parse --show-toplevel`). If they differ, warn: "mill-go is running from `<cwd>` but the discussion was written in `<worktree>`. Verify you are in the correct worktree." This is the one exception to the "never ask" rule --- worktree mismatch can destroy work.

Extract the `task:` field from the YAML code block in status.md to identify the task title.

`mill-go` is always autonomous. It never runs a discuss phase or asks clarifying questions. That is `mill-start`'s job.

**Never ask for permission or confirmation during execution.** Do not say "Want me to continue?", "Should I proceed?", "Shall I fix this?". The only valid stopping points are listed in "Stops when" below. Everything else --- just do it.

---

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `-pr N` | `3` | Maximum number of plan review rounds. `-pr 0` skips plan review entirely. |
| `-cr N` | `3` | Maximum number of code review rounds. `-cr 0` is passed through to Thread B and skips Phase: Review there. |

Parse `-pr` and `-cr` values from the skill invocation arguments. If not provided via CLI, read `reviews.plan` and `reviews.code` from `_millhouse/config.yaml` as defaults. CLI args override config. If neither is set, default to `3`. Store as `max_plan_review_rounds` and `max_code_review_rounds`. `max_code_review_rounds` is passed to Thread B via the implementer brief; mill-go itself never enforces it.

---

## Resume Protocol

mill-go's resume scope is **Pre-Setup only** — Phase: Plan and Phase: Plan Review. Post-Setup resume (the implementation, test, and code-review phases) lives in Thread B and is handled per `plugins/mill/doc/modules/implementer-brief.md`. mill-go does not re-enter Thread B's domain.

On entry, check the `phase:` field in `_millhouse/task/status.md`:

- **`phase: discussed`, no `plan:` field in status.md:** Phase: Plan (plan not yet written). Re-write the plan from scratch using the discussion file.
- **`phase: discussed`, `plan:` field exists, plan frontmatter has `approved: false`:** Phase: Plan Review (plan written, not yet approved). Re-enter the plan review loop with the existing plan.
- **`phase: discussed`, `plan:` field exists, plan frontmatter has `approved: true`:** plan approved but phase not yet updated → enter Phase: Setup normally.
- **`phase: planned`:** plan approved and phase written, Phase: Setup not yet complete → enter Phase: Setup (skip the `approved: true` check).
- **`phase: implementing`, `testing`, `reviewing`, or `blocked`:** Thread B's domain. Report the current state from status.md and stop. Do not re-spawn automatically. Re-spawning is a manual action — the user re-runs mill-go after verifying Thread B's state.

**Thread B double-spawn guard.** Before entering Phase: Spawn Thread B from a `phase: planned` resume, check the timeline text block in `_millhouse/task/status.md` for an existing `thread-b-spawn` entry. If found: a prior spawn occurred in this session (Thread A was interrupted in the handoff window after spawn but before `phase: implementing` was written). Do **not** re-spawn — instead report:

> Thread B was already spawned (thread-b-spawn timestamp found in status.md). Current phase is still `planned`, which means Thread B may still be running or may have exited. Check `_millhouse/task/status.md` and re-run mill-go with explicit intent when Thread B's state is confirmed.

and stop.

Test baseline capture is handled by Thread B per `plugins/mill/doc/modules/implementer-brief.md`. mill-go does not capture or read the baseline.

---

## Phases

mill-go proceeds through named phases. Each phase updates the YAML code block in `_millhouse/task/status.md` with the current phase name and relevant fields, and inserts timeline entries before the closing ` ``` ` of the timeline text block.

### Phase: Plan

0. Read the discussion file for all context: problem, approach, decisions, constraints, technical context, testing strategy, Q&A log, config.

1. **Write the implementation plan.** Generate the timestamp via shell (see `@mill:cli` timestamp rules — never guess timestamps):
   ```bash
   TS=$(date -u +"%Y%m%d-%H%M%S")
   ```
   Use `$TS` for the `started:` frontmatter field.

   Write the plan to `_millhouse/task/plan.md` per the schema in `plugins/mill/doc/modules/plan-format.md`. **Each step card must satisfy the atomicity invariant** — the extraction test in `plan-format.md` must pass for every card. Verbosity is the feature; repetition across cards is acceptable when it lets a fresh agent implement one card without reading another.

   **Writing `## Context`:** Copy decisions from the discussion file's `## Decisions` section. Each `### Decision:` subsection must have `**Why:**` and `**Alternatives rejected:**`. These are what reviewers check against.

   Include quality & testing strategy from the discussion file. Each step touches a small, reviewable scope. Never bundle unrelated file operations into a single step.

   Write the full plan autonomously --- no incremental approval checkpoints.

   Update the YAML code block in status.md: add `plan: _millhouse/task/plan.md`.

### Phase: Plan Review (BLOCKING GATE) (round N/max_plan_review_rounds)

**If `max_plan_review_rounds` is `0`:** skip Phase: Plan Review entirely. Set `approved: true` in plan frontmatter and proceed to Phase: Setup.

| Thought that means STOP | Reality |
|---|---|
| "The plan looks good, I'll skip review" | Run the review subagent. Every time. **No exceptions.** |
| "This is a simple change, review isn't needed" | Simple changes have the most unexamined assumptions. Review anyway. |
| "I'll save time and go straight to Setup" | Time saved here is bugs shipped later. Run the gate. |

**Verification:** You MUST have spawned the plan-reviewer before proceeding to Phase: Setup. If you have not, go back and run Phase: Plan Review now.

2. **Plan review loop:**

   **Setup:** Ensure `_millhouse/task/reviews/` directory exists (`mkdir -p` if not). Initialize `prev_fixer_report_path` to empty (no previous fixer report on first round).

   a. Report to user: **"Plan Review --- round N/&lt;max_plan_review_rounds&gt;"** (where N is the current round number, starting at 1)

   b. Read `CONSTRAINTS.md` from repo root (via `git rev-parse --show-toplevel`) if it exists.

   c. **Resolve the reviewer name for round N.** Prefer `review-modules.plan.<N>` from `_millhouse/config.yaml`; if absent, fall back to `review-modules.plan.default`. For legacy configs without `review-modules:`, fall back to `models.plan-review.<N>|default` and wrap as `single-<modelname>` (if a matching `reviewers.single-<modelname>` entry exists) or pass as `--reviewer-name` directly. The integer key is compared as a string. See `plugins/mill/doc/overview.md#config-resolution`.

   d. **Materialize the prompt.** Read the prompt template from `plugins/mill/doc/modules/plan-review.md`. Substitute `<PLAN_FILE_PATH>` (absolute path to `_millhouse/task/plan.md`), `<TASK_TITLE>` (from status.md), `<CONSTRAINTS_CONTENT>` (CONSTRAINTS.md content or `(no CONSTRAINTS.md)`), and `<N>` (current round number). Write the materialized prompt to `_millhouse/scratch/plan-review-prompt-r<N>.md`. **Do NOT inline the plan content** — the reviewer reads the plan file independently.

   e. **Spawn the plan-reviewer.** Invoke via Bash (synchronous, not backgrounded):
      ```bash
      python plugins/mill/scripts/spawn-reviewer.py --reviewer-name <reviewer-name> --prompt-file _millhouse/scratch/plan-review-prompt-r<N>.md --phase plan --round <N>
      ```

   f. **Parse the JSON line** from the script's stdout: `{"verdict": "APPROVE" | "REQUEST_CHANGES", "review_file": "<absolute-path>"}`.

   g. If verdict is **APPROVE**: set `approved: true` in plan frontmatter. Update the YAML code block in status.md: `phase: planned`. Use the Edit tool to insert `plan-review-r<N>  <timestamp>` and then `planned  <timestamp>` on new lines before the closing ` ``` ` of the timeline text block in status.md. Proceed to Phase: Setup. Do not read the review file.

   h. If verdict is **REQUEST_CHANGES**:
      1. **Invoke the `mill-receiving-review` skill** via the Skill tool. This is mandatory before evaluating any finding — it loads the decision tree you must apply.
      2. Read the review report from `review_file`.
      3. For each BLOCKING finding, apply the receiving-review decision tree: VERIFY accuracy (cite actual code if inaccurate), then HARM CHECK (breaks functionality / conflicts with documented design decision / destabilizes out-of-scope code). If none apply: FIX IT. If harm found: PUSH BACK with cited evidence.
      4. Apply fixes inline to the plan file. Check systemic implications — a fix in one step may require updates to other steps or decisions.
      5. Write a fixer report to `_millhouse/task/reviews/<timestamp>-plan-fix-r<N>.md` with `## Fixed` and `## Pushed Back` sections. Format:
         ```markdown
         # Plan Fix Report --- Round <N>

         ## Fixed
         - Finding <N>: what was changed and where in the plan

         ## Pushed Back
         - Finding <N>: evidence why the fix would cause harm (cite code/docs)
         ```

   i. **Progress detection.** Update `prev_fixer_report_path` to the current fixer report path. If `prev_fixer_report_path` was set before this round: read the `## Pushed Back` section from the previous fixer report and compare it against the `## Pushed Back` section from the current fixer report. If the pushed-back findings are identical (same finding numbers and descriptions), non-progress is detected: update the YAML code block in `_millhouse/task/status.md` with `blocked: true`, `blocked_reason: Plan review non-progress — agent pushed back identical findings in consecutive rounds`, `phase: blocked`. Use the Edit tool to insert `blocked  <timestamp>` before the closing ` ``` ` of the timeline text block. Run the **Notification Procedure** with `BLOCKED: Plan review non-progress after consecutive rounds`. Escalate to user immediately rather than spending remaining rounds.

   j. Insert `plan-review-r<N>  <timestamp>` and `plan-fix-r<N>  <timestamp>` lines before the closing ` ``` ` of the timeline text block in status.md.

   k. Re-spawn the reviewer with the **updated plan only**. Do NOT pass the fixer report path. The reviewer always starts fresh from the updated plan alone, with no context from prior rounds. Report: **"Plan Review --- round N/&lt;max_plan_review_rounds&gt;"**

   l. Max `max_plan_review_rounds` rounds. If unresolved BLOCKING issues remain after all rounds: this likely indicates a design flaw rather than something fixable with another review round. Update the YAML code block in `_millhouse/task/status.md` with `blocked: true`, `blocked_reason: Plan review dispute after <max_plan_review_rounds> rounds`, `phase: blocked`. Use the Edit tool to insert `blocked  <timestamp>` before the closing ` ``` ` of the timeline text block. Run the **Notification Procedure** with `BLOCKED: Plan review dispute after <max_plan_review_rounds> rounds`. Present remaining BLOCKING issues to user for decision.

### Phase: Setup

3. Record `PLAN_START_HASH=$(git rev-parse HEAD)`. Store in the YAML code block of `_millhouse/task/status.md` as `plan_start_hash:`. On resume, read from the YAML code block in status.md instead of re-computing.

4. Read plan (path from the YAML code block in `_millhouse/task/status.md` `plan:` field). Read all files listed in `## Files`.

5. **Staleness check.** Run `git log --since=<started> -- <file1> <file2> ...` using the `started:` timestamp from plan frontmatter and files from `## Files`.
   - No changes: proceed.
   - Minor changes (formatting, comments, unrelated areas): log warning in status.md, proceed.
   - Major changes (files restructured, APIs changed, interfaces modified): halt. Plan-stale revert:
     1. Resolve parent worktree path via `git worktree list --porcelain` or the `parent:` field from the YAML code block in `_millhouse/task/status.md`.
     2. Update the YAML code block in `_millhouse/task/status.md` with `blocked: true`, `blocked_reason: Plan stale --- files changed since plan was written`, `phase: blocked`. Use the Edit tool to insert `blocked  <timestamp>` before the closing ` ``` ` of the timeline text block. Run the **Notification Procedure** with `BLOCKED: Plan stale — files changed`. Tell the user to re-run `mill-start`.
     3. **Note:** mill-go no longer updates the parent's `tasks.md` on plan-stale revert. The `[active]` marker written at claim time remains in place — the task is still active (just blocked). Tasks.md is only touched at merge (`[done]`) or abandon (`[abandoned]`).

6. **Read constraints.** Resolve repo root: `git rev-parse --show-toplevel`. Read `CONSTRAINTS.md` from repo root if it exists. These are hard invariants — Thread B will receive a copy. If the file does not exist, proceed without it.

7. **Phase: Setup no longer updates the parent's `tasks.md`.** The `[active]` marker written at claim time (by `mill-start` or `mill-spawn.ps1`) remains in place throughout Thread B's implementation and is replaced only by `mill-merge` (`[done]`) or `mill-abandon` (`[abandoned]`). mill-go does not participate in tasks.md writes during Phase: Setup.

### Phase: Spawn Thread B

8. **Materialize the implementer brief.** Read the brief template from `plugins/mill/doc/modules/implementer-brief.md`. Substitute the runtime tokens listed in that file's "Substitution Tokens" table:
   - `<PLAN_PATH>` → absolute path to `_millhouse/task/plan.md`
   - `<STATUS_PATH>` → absolute path to `_millhouse/task/status.md`
   - `<WORK_DIR>` → output of `git rev-parse --show-toplevel`
   - `<REPO_ROOT>` → same as `<WORK_DIR>`
   - `<VERIFY_CMD>` → the `verify:` value from plan frontmatter
   - `<MAX_CODE_REVIEW_ROUNDS>` → the resolved `max_code_review_rounds` value
   - `<CODE_REVIEW_RESOLUTION_SNAPSHOT>` → the `review-modules.code` block from `_millhouse/config.yaml`, copied verbatim (maps round numbers to reviewer names). For legacy configs without `review-modules:`, fall back to copying the `models.code-review` block.
   - `<TASK_TITLE>` → task title from status.md

   Write the materialized brief to `_millhouse/task/implementer-brief-instance.md`.

9. **Resolve the implementer model.** Read `models.implementer` from `_millhouse/config.yaml` (scalar, no per-round indirection).

10. **Update status.md `phase: implementing`.** Insert `implementing  <timestamp>` and then `thread-b-spawn  <timestamp>` on new lines before the closing ` ``` ` of the timeline text block. The two timeline entries are written together — the `thread-b-spawn` line is the double-spawn-guard signal for any subsequent resume.

11. **Spawn Thread B.** Invoke the Bash tool with `run_in_background: true`:
    ```bash
    powershell.exe -File plugins/mill/scripts/spawn-agent.ps1 -Role implementer -PromptFile _millhouse/task/implementer-brief-instance.md -ProviderName <implementer-model>
    ```

12. **Capture the background shell ID.** Use the `Monitor` tool on that shell ID to wait for completion. While monitoring, periodically read `_millhouse/task/status.md` and relay each `current_step` change to the user as a brief progress line.

13. **Stall detection.** If `Monitor` produces no output AND `_millhouse/task/status.md` mtime has not advanced for 10 minutes, report:

    > Thread B appears stalled. Status: `<last phase>`. Manual intervention required.

    and stop. The 10-minute threshold is configurable via `timeouts.implementer-stall-minutes` in `_millhouse/config.yaml` (optional; default 10 if missing).

14. **On Thread B exit:**
    - **Spawn-script exits 0:** read the script's stdout JSON line: `{"phase": ..., "status_file": ..., "final_commit": ...}`. Extract `phase` and `final_commit`. Read `_millhouse/task/status.md` for the authoritative `phase:` value. **If they disagree, trust status.md and report the discrepancy to the user.** Transition to Phase: Completion below.
    - **Spawn-script exits non-zero before Thread B entered Phase: Implement** (early failure: e.g. claude CLI failed, prompt file missing, JSON wrapper unparseable): report "Thread B spawn failed: <stderr from Monitor>" and stop. Update `_millhouse/task/status.md` with `blocked: true`, `blocked_reason: Thread B spawn failure`, `phase: blocked`. Insert `blocked  <timestamp>` in the timeline. Run the **Notification Procedure** with `BLOCKED: Thread B spawn failure`. Stop.
    - **Spawn-script exits non-zero with `phase: blocked` already in status.md** (mid-run failure): read `blocked_reason`, relay to user, stop. Notification was already sent by Thread B before exit.

### Phase: Completion

15. After Thread B returns, mill-go finalizes its own session:

    a. Read `_millhouse/task/status.md` `phase:`. Expected values: `complete`, `blocked`, `pr-pending`.

    b. **`complete`:** report:
       > Task complete. Final commit: `<final_commit>`. Phase: complete.

       Exit cleanly. Notification was already sent by Thread B (mill-merge if child worktree, in-place finalize if main worktree).

    c. **`blocked`:** report `blocked_reason` from status.md, exit. Notification was already sent.

    d. **`pr-pending`:** report:
       > Task complete; PR pending. Run `gh pr view` for details.

       Exit. Notification was already sent by mill-merge.

    e. Thread A's responsibilities end here. **Do not invoke `mill-merge` directly** — Thread B does that.

---

## Stops When

mill-go (Thread A) stops in any of these situations:

- **Plan reviewer blocks** after `max_plan_review_rounds` rounds → block, notify, stop
- **Plan stale** (major changes to listed files in `## Files`) → block, tell user to re-run mill-start
- **Thread B spawn failure** (script exits non-zero before Thread B enters Phase: Implement) → block, notify, stop
- **Thread B reports blocked** (script exits non-zero with `phase: blocked` in status.md) → relay reason, stop. Notification already sent by Thread B
- **Thread B stall** (no Monitor output AND status.md mtime stale for 10+ minutes) → report and stop
- **Thread B completes** (`phase: complete` or `pr-pending`) → report final state and exit

Implementation, test, and code-review failures are Thread B's domain — they appear here only as "Thread B reports blocked".

---

## Board Updates

tasks.md changes require commit and push (tasks.md is git-tracked). When running from a child worktree, resolve the parent's project root by computing the project subdirectory offset (working directory minus git root) and applying it to the parent worktree path from `git worktree list --porcelain`. Modify the parent's `tasks.md` at that project root.

Phase transitions are tracked via `phase:` in the YAML code block of `_millhouse/task/status.md` and the `## Timeline` section (entries inserted before the closing ` ``` ` of the text fence). See `doc/modules/discussion-format.md` for the status.md schema and timeline format.

mill-go (Thread A) does not write `[implementing]` or any other marker to the parent's `tasks.md`. The claim marker `[active]` is written at claim time by `mill-start` / `mill-spawn.ps1`; `mill-merge` writes `[done]` on successful merge; `mill-abandon` writes `[abandoned]` on abandonment. mill-go does not participate in tasks.md writes.

**Plan stale:** mill-go updates `_millhouse/task/status.md` with `blocked: true` but does NOT remove or modify the `[active]` marker in the parent's tasks.md. The task is still active (just blocked).

---

## Notification Procedure

When the skill says "notify user", follow this procedure. Notifications are NOT a separate skill — they are inline calls made at specific points in mill-go.

### Step 1: Update status file (always)

Write the event to the YAML code block in `_millhouse/task/status.md`. This happens regardless of config — the status file is the most reliable channel.

For blocking events, ensure `blocked: true` and `blocked_reason:` are set.

### Step 2: Send notification

Run the `notify.sh` script. It reads `_millhouse/config.yaml`, detects the platform, and sends a desktop toast (and Slack, when enabled). Best-effort — failures warn on stderr, never block execution.

```bash
bash "$(git rev-parse --show-toplevel)/plugins/mill/scripts/notify.sh" \
  --event "<EVENT>" \
  --branch "$(git branch --show-current)" \
  --detail "<detail>" \
  --urgency "<info|high>"
```

Replace `<EVENT>` with `BLOCKED` or `COMPLETE`, `<detail>` with the reason, and `<urgency>` with `high` (blocking events) or `info` (completion events).

### When to notify (mill-go / Thread A only)

| Call site | Event | Urgency |
|-----------|-------|---------|
| Phase: Plan Review — non-progress after consecutive fixer rounds | `BLOCKED: Plan review non-progress` | High |
| Phase: Plan Review — dispute after max rounds | `BLOCKED: Plan review dispute` | High |
| Phase: Setup — plan stale | `BLOCKED: Plan stale — files changed` | High |
| Phase: Spawn Thread B — spawn-script early failure | `BLOCKED: Thread B spawn failure` | High |
| Phase: Spawn Thread B — Thread B stall (no Monitor or status.md activity for N minutes) | `BLOCKED: Thread B stalled` | High |

Thread B's own call sites (test failure, code reviewer dispute, merge failure, completion) live in `plugins/mill/doc/modules/implementer-brief.md` `### 11. Notification Procedure`. Thread B sends those notifications itself; mill-go relays the blocked state and exits.

---

## Systematic Debugging Protocol

The Systematic Debugging Protocol applies during **Thread B's** Phase: Implement. See `plugins/mill/doc/modules/implementer-brief.md` `### 9. Systematic Debugging Protocol` for the full protocol. mill-go (Thread A) does not debug code — it only spawns and reports.

---

## Failure Classification

The Failure Classification taxonomy applies during **Thread B's** Phase: Implement. See `plugins/mill/doc/modules/implementer-brief.md` `### 10. Failure Classification`. mill-go (Thread A) classifies its own failures as one of three types: plan-review escalation, plan staleness, or Thread B spawn / monitoring failure — all handled inline above.

---

## Post-Failure State

On any Thread A failure that blocks progress:

1. Update the YAML code block in `_millhouse/task/status.md` with `blocked: true`, `blocked_reason:`, and `phase: blocked`. Use the Edit tool to insert `blocked  <timestamp>` before the closing ` ``` ` of the timeline text block.
2. Preserve all state --- do not clean up, do not rollback automatically.
3. Run the **Notification Procedure** (see section above) with the BLOCKED event.
4. Report the blocker to the user.
