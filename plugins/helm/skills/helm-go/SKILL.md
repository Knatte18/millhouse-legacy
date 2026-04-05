---
name: helm-go
description: Execute an approved plan autonomously. Session agent.
argument-hint: "[-r N]"
---

# helm-go

You are a session agent. You implement the approved plan autonomously --- exploring code, writing implementations, running tests, and submitting your work for independent code review. You do not inspect your own work; a separate reviewer agent does that. You stop the line when something breaks and escalate when you cannot resolve a problem.

Autonomous. Execute the plan.

For kanban.md file format details, see `plugins/helm/doc/modules/kanban-format.md`.

---

## Entry

Read `_helm/config.yaml`. If it does not exist, stop --- tell the user to run `helm-setup` first.

Read `_helm/scratch/status.md`. Extract the `plan:` field to locate the plan file and `task:` field to identify the task title.

Read the plan file. If it does not exist, stop --- tell the user to re-run `helm-start`. Check `approved: true` in frontmatter. If not approved, refuse --- tell the user to run `helm-start` first.

`helm-go` is always autonomous. It never runs a discuss phase or asks clarifying questions. That is `helm-start`'s job.

**Never ask for permission or confirmation during execution.** Do not say "Want me to continue?", "Should I proceed?", "Shall I fix this?". The only valid stopping points are listed in "Stops when" below. Everything else --- just do it.

---

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `-r N` | `5` | Maximum number of code review rounds. `-r 0` skips code review entirely (Phase: Review and Phase: Resolve are not executed). |

Parse the `-r` value from the skill invocation arguments. If not provided, default to `5`. Store the value as `max_review_rounds` for use in Phase: Review.

---

## Resume Protocol

On entry, check if this is a resume (prior work exists):

1. Check `git log --oneline` for commits matching plan step `Commit:` messages.
2. For each matching commit: mark that step as already done --- skip it.
3. Read `_helm/scratch/status.md` for `phase:`, `current_step:`, and retry counts under `retries:`.
4. Determine current phase from the task's column position in `kanbans/board.kanban.md`:
   - Task in `## Planned` → Phase: Setup (about to start)
   - Task in `## Implementing` → Phase: Implement (resume from current_step)
   - Task in `## Testing` → Phase: Test
   - Task in `## Reviewing` → Phase: Review
   - Task in `## Blocked` → report blocker from status.md and stop
5. Continue from the first incomplete step.

Do NOT redo completed work. Do NOT re-run tests for steps that already committed successfully.

---

## Test Baseline

Before implementing any steps (and only if not resuming past this point), capture the test baseline:

1. Run the full test suite (`verify` command from plan frontmatter).
2. Record which tests fail (if any) to `_helm/scratch/test-baseline.md`.
3. If all pass: write "All tests pass --- clean baseline."
4. If verify command isn't runnable yet (missing dependencies, not buildable): write "No baseline --- not yet buildable."

During implementation, if a test failure matches the baseline (pre-existing), do not count it as a regression. Only new failures trigger retries.

---

## Phases

helm-go proceeds through named phases. Each phase updates `_helm/scratch/status.md` with the current phase name and relevant fields. On resume, the agent reads the phase from status.md and continues from there.

### Phase: Setup

0. Record `PLAN_START_HASH=$(git rev-parse HEAD)`. Store in `_helm/scratch/status.md` as `plan_start_hash:`. On resume, read from status.md instead of re-computing.

1. Read plan (path from `_helm/scratch/status.md` `plan:` field). Read all files listed in `## Files`.

2. **Staleness check.** Run `git log --since=<started> -- <file1> <file2> ...` using the `started:` timestamp from plan frontmatter and files from `## Files`.
   - No changes: proceed.
   - Minor changes (formatting, comments, unrelated areas): log warning in status.md, proceed.
   - Major changes (files restructured, APIs changed, interfaces modified): halt. Plan-stale revert:
     1. Resolve parent worktree path via `git worktree list --porcelain` or `_helm/scratch/status.md` `parent:` field.
     2. Check for modifications: `git -C <parent-path> status --porcelain kanbans/backlog.kanban.md` — if output is non-empty, report the conflict and stop. Task remains on work-board (no data loss).
     3. Add task back to `## Backlog` in the **parent's** `kanbans/backlog.kanban.md`. Commit and push from parent context: `git -C <parent-path> add kanbans/backlog.kanban.md && git -C <parent-path> commit -m "revert: return <task> to backlog (plan stale)" && git -C <parent-path> push`
     4. Only after the backlog commit succeeds: remove task from `kanbans/board.kanban.md`.
     5. Recovery: if the backlog write/commit fails at step 3, stop and report the error. The task stays on the work-board — no data is lost. The user can retry or manually move the task.
     6. Update status.md with `blocked: true` and `blocked_reason: Plan stale --- files changed since plan was written`. Run the **Notification Procedure** with `BLOCKED: Plan stale — files changed`. Tell the user to re-run `helm-start`.

3. **Explore.** Read code following each step's `Explore:` targets. Read accumulated knowledge from `_helm/knowledge/` if the directory has entries — if `_helm/knowledge/summary.md` exists, read only the summary (not individual entries); otherwise read all entries. If `_codeguide/Overview.md` exists: read it and use the navigation pattern (Overview -> module doc -> Source section -> code).

4. **Read constraints.** Resolve repo root: `git rev-parse --show-toplevel`. Read `CONSTRAINTS.md` from repo root if it exists. These are hard invariants — never write code that violates them. If the file does not exist, proceed without it.

5. **Move to Implementing.** Move task from `## Planned` to `## Implementing` in `kanbans/board.kanban.md` (column move — no phase suffix). Validate per `doc/modules/validation.md` (6-column rules: Discussing, Planned, Implementing, Testing, Reviewing, Blocked). If validation fails, report the issue to the user and stop.

   Update `_helm/scratch/status.md`:
   ```
   phase: implementing
   current_step: 1
   ```

### Phase: Implement

6. **For each step in the plan:**

   a. Update `_helm/scratch/status.md` with current step number and name:
      ```
      current_step: <N>
      current_step_name: <step description>
      ```

   b. Read the step's `Explore:` targets if not already read during Setup.

   c. **If TDD-marked** (step has `TDD: RED -> GREEN -> REFACTOR`):
      1. **RED:** Write the test first. Run the test suite. Confirm the new test FAILS.
         - If the new test passes immediately: STOP --- the test is wrong (it's not testing new behavior). Fix the test before proceeding.
      2. **GREEN:** Implement the minimum code to make the test pass. Run the test suite. Confirm the new test passes.
      3. **REFACTOR:** Clean up the implementation, keeping all tests green. Run the test suite after refactoring.

   d. **If not TDD-marked:** Implement the step's requirements. Run the test suite.

   e. **On test failure** (new failure, not in baseline):
      1. Invoke the Systematic Debugging Protocol (see below) before retrying.
      2. Track retry count in `_helm/scratch/status.md` under `retries:` as `step_<N>: <count>`.
      3. Max 3 retries per step.
      4. After 3 retries: classify the failure and route:
         - **Code error** that you cannot fix: update status.md with `blocked: true`, `blocked_reason:`. Move task from current column to `## Blocked` in `kanbans/board.kanban.md`. Validate per `doc/modules/validation.md` (6-column rules). Stop.
         - **Permission/config error**: notify user immediately (no retries were appropriate). Update status.md. Move task to `## Blocked`. Validate. Stop.
         - **Upstream dependency error** (import from non-existent file, API not available): update status.md. Move task to `## Blocked`. Validate. Stop.

   f. **Commit and push after each successful step** using the step's `Commit:` message:
      - Stage files individually: `git add file1 file2` --- never `git add .` or `git add -A`.
      - Commit: `git commit -m "<commit message from step>"`
      - Push: `git push`
      - This enables resume on crash.

   On any block (after 3 retries, permission error, upstream dependency): after updating status.md and kanban, run the **Notification Procedure** with the appropriate BLOCKED event.

### Phase: Test

7. Move task from `## Implementing` to `## Testing` in `kanbans/board.kanban.md` (column move). Validate per `doc/modules/validation.md` (6-column rules). Update `_helm/scratch/status.md`:
   ```
   phase: testing
   ```

   **Full verification.** Run the complete verify command from plan frontmatter (lint, type-check, build, test --- whatever the command includes).
   - All tests must pass --- not just tests related to this task.
   - Compare failures against `_helm/scratch/test-baseline.md` to distinguish pre-existing failures from new regressions.
   - If new failures: debug and fix using the Systematic Debugging Protocol. Max 3 retries for the full verification. If unresolved: move task to `## Blocked`, update status.md, run Notification Procedure, stop.

   **If `max_review_rounds` is `0`:** skip Phase: Review and Phase: Resolve entirely. Proceed directly to Phase: Finalize.

### Phase: Review (round N/max_review_rounds)

8. Update `_helm/scratch/status.md`:
   ```
   phase: reviewing
   ```

   Move task from `## Testing` to `## Reviewing` in `kanbans/board.kanban.md` (column move). Validate per `doc/modules/validation.md` (6-column rules).

9. **Spawn code-reviewer Agent.** Use the Agent tool with `model: sonnet`. Report to user: **"Review --- round 1/&lt;max_review_rounds&gt;"**

   Compute the diff: `git diff <plan_start_hash>..HEAD`

   Read `_codeguide/Overview.md` if it exists (pass content to reviewer). Read `_helm/knowledge/` entries if they exist (pass content to reviewer). Read `CONSTRAINTS.md` from repo root (via `git rev-parse --show-toplevel`) if it exists (pass content to reviewer).

   Pass the following prompt verbatim, substituting `<DIFF>`, `<PLAN_CONTENT>`, `<OVERVIEW_CONTENT>`, `<KNOWLEDGE_CONTENT>`, and `<CONSTRAINTS_CONTENT>`:

   ---
   You are an independent code reviewer. Evaluate the submitted diff for production readiness. You have no shared context with the implementing agent --- you see only the diff, the plan, and the quality standards. Be thorough, critical, and constructive.

   **FIRST ACTION --- mandatory before anything else:**
   Read `_codeguide/Overview.md` if it exists. Use its module table and routing hints to navigate to relevant source files. If it does not exist, proceed without it.

   **Context provided:**

   1. The approved plan:
   <PLAN_CONTENT>

   2. Codeguide Overview (if available):
   <OVERVIEW_CONTENT>

   3. Knowledge from prior tasks (if available):
   <KNOWLEDGE_CONTENT>

   4. Repository constraints (if available):
   <CONSTRAINTS_CONTENT>

   5. The diff to review:
   <DIFF>

   **Evaluate the diff against these criteria:**

   - **Plan alignment:** Does the code match the plan? Are there steps in the plan that the diff doesn't implement, or code in the diff that the plan doesn't describe?
   - **Design intent:** For each `### Decision:` subsection in the plan's `## Context`, verify the implementation reflects the stated choice and does not silently deviate. Flag deviations as BLOCKING.
   - **Correctness:** Bugs, logic errors, off-by-one errors, null/undefined handling?
   - **Dead code:** Unused exports, unimported files, unreachable branches?
   - **Test thoroughness** (enforce `@code:testing` rules):
     - Happy-path-only tests -> BLOCKING. Error paths and edge cases from plan's `Key test scenarios` must be covered.
     - Implementation-mirroring tests (testing internal state instead of observable behavior) -> BLOCKING.
     - Shallow assertions (`assert result`, `assert result is not None`) -> BLOCKING.
     - TDD-marked steps where diff shows implementation committed without a preceding failing test -> BLOCKING.
   - **Utility duplication** (BLOCKING): For every new function, helper, or utility in the diff, grep the codebase for existing implementations with similar names or purposes. Use the codeguide Overview to identify which modules to check. If an existing utility covers the same functionality, flag the reimplementation as BLOCKING with a pointer to the existing implementation.
   - **Constraint violations** (BLOCKING): Check every constraint in the constraints section. If the diff introduces code that violates any constraint, flag as BLOCKING with the constraint heading and the violating code.
   - **Pattern consistency:** Check that new code follows the same patterns as existing code in the same area --- naming conventions, error handling style, authentication patterns on endpoints.
   - **Codebase consistency:** Does the code follow existing patterns in the codebase?

   **Output format:**

   For each finding:
   - State the file and line(s) it applies to
   - State severity: **BLOCKING** (must fix before merge) or **NIT** (nice-to-have improvement)
   - Describe the issue and suggest a fix

   End with per-file observations (one sentence per file changed) and an overall verdict: **APPROVE** or **REQUEST CHANGES**.
   - APPROVE means: no BLOCKING issues remain. NITs are noted but do not block. Must include per-file observations --- a bare "APPROVE" without per-file analysis is invalid.
   - REQUEST CHANGES means: one or more BLOCKING issues must be addressed.

   Return only the review report. No preamble, no closing remarks.
   ---

10. **Before reading the reviewer's findings**, invoke the `helm-receiving-review` skill via the Skill tool. This is **mandatory** --- it loads the decision tree into context before evaluation begins. Loading it after reading findings is useless; you will have already formed rationalizations.

11. Read the reviewer's findings. Verify the reviewer's verdict is substantiated --- output must contain per-file observations. A bare "APPROVE" without per-file analysis is treated as a failed review; re-spawn the reviewer. Spawn a **fixer agent** to apply BLOCKING fixes — do not fix inline yourself (fresh eyes catch systemic implications better).

12. If reviewer **approves** (no BLOCKING issues): proceed to Phase: Finalize.

### Phase: Resolve (round N/max_review_rounds)

13. If reviewer **requests changes**: report **"Resolve --- round N/&lt;max_review_rounds&gt;"**

14. Spawn a fixer agent with: (1) full list of BLOCKING findings, (2) affected file paths, (3) instruction to check systemic implications. The fixer applies fixes directly. Do not fix inline yourself.

15. Re-run full verification (the verify command from plan frontmatter).

16. Re-spawn code-reviewer Agent with the updated diff (`git diff <plan_start_hash>..HEAD`). Report: **"Review --- round N/&lt;max_review_rounds&gt;"**

17. Max `max_review_rounds` rounds. If unresolved BLOCKING issues after all rounds: this likely indicates a design flaw rather than something fixable with another review round. Escalate to user. Update status.md with `blocked: true`, `blocked_reason: Review dispute after <max_review_rounds> rounds — likely design flaw`. Move task to `## Blocked` in `kanbans/board.kanban.md`. Validate per `doc/modules/validation.md` (6-column rules). Run the **Notification Procedure** with `BLOCKED: Code reviewer dispute after <max_review_rounds> rounds`. Report both sides to user:
    ```
    Code reviewer flagged: "<finding>"
    Implementing agent's position: "<reasoning>"
    ```

### Phase: Finalize

18. **Codeguide update.** If `_codeguide/Overview.md` exists, invoke the `codeguide:codeguide-update` skill (no arguments --- it defaults to the current git diff).

19. **Write knowledge entry.** Create `_helm/knowledge/<worktree-slug>-<timestamp>-<topic>.md` where:
    - `<worktree-slug>` is the current branch name slugified (e.g. `feature-auth-oauth`)
    - `<timestamp>` is UTC `YYYYMMDD-HHMMSS`
    - `<topic>` is a short slug for the task (e.g. `oauth-client`)

    Content:
    ```markdown
    # Task: <title>

    ## Shared utilities created
    - (list any new shared utilities with file paths and signatures)

    ## Patterns established
    - (list any new conventions established)

    ## Existing patterns discovered
    - (list existing codebase patterns that weren't obvious)

    ## Gotchas
    - (list things that caused wasted time or were surprising)
    ```

    Include only categories that have content. If nothing was learned, skip this step.

20. **Record architectural decisions.** If any steps involved architectural choices (where a future session might ask "why did they do it this way?"), append to `_helm/knowledge/decisions.md`:

    ```markdown
    ## [Step N] Decision title
    **Why:** Reasoning behind the choice
    **Trade-off:** What was traded off
    **Alternatives rejected:** What else was considered and why not
    ```

    Create the file if it doesn't exist.

21. **Post-review commit.** If any files changed during review fixes, codeguide update, or knowledge writing:
    - Stage files individually: `git add file1 file2` --- never `git add .` or `git add -A`.
    - Commit: `chore: post-review cleanup for <task-title>`
    - Push: `git push`

22. **Update status.md:**
    ```
    phase: complete
    ```

23. **Remove task from board.** Remove the task block from `kanbans/board.kanban.md` entirely — do not move to a Done column (there is none). Validate per `doc/modules/validation.md` (6-column rules). If validation fails, report the issue to the user and stop.

24. **Knowledge synthesis.** If `_helm/knowledge/` contains more than 5 entries (excluding `decisions.md` and `summary.md`):
    1. Read all entries.
    2. Deduplicate (multiple tasks may discover the same pattern).
    3. Resolve conflicts (if tasks established contradictory patterns, pick the winner).
    4. Write consolidated `_helm/knowledge/summary.md`.
    5. Subsequent tasks read only the summary, not individual entries.

---

## Completion

When no more planned tasks remain:

1. Set `_helm/scratch/status.md` phase to `ready-to-merge`.
2. Run the **Notification Procedure** with `COMPLETE: All tasks done, ready to merge` (info-level — toast + status only, skip Slack).
3. Report to user: `[helm] ready to merge --- all tasks complete.`

---

## Stops When

- All tasks complete -> completion flow
- Test failure after 3 retries -> block, notify user
- Code reviewer blocks after `max_review_rounds` rounds with unresolvable issues -> block, notify user
- Permission/config error -> block, notify user immediately (no retries)
- Plan staleness (major changes to listed files) -> block, tell user to re-run helm-start

---

## Kanban Updates

Work board changes (`kanbans/board.kanban.md`) are local-only (gitignored). No git staging needed.

Backlog changes (`kanbans/backlog.kanban.md`) are git-tracked — commit and push after every write. Use `git -C <parent-path>` when writing from a child worktree.

Column moves in `kanbans/board.kanban.md` (no `[phase]` suffixes — column IS the phase):
- Setup starts → task in `## Planned` (already moved by helm-start), move to `## Implementing`
- Implement → Test → move from `## Implementing` to `## Testing`
- Test → Review → move from `## Testing` to `## Reviewing`
- Finalize → remove task from board entirely (no Done column)
- Plan stale → remove from board, add back to parent's `backlog.kanban.md` `## Backlog` (with git commit)
- Blocked → move to `## Blocked` from whatever current column

Validate per `doc/modules/validation.md` (6-column rules) after every board write.

---

## Notification Procedure

When the skill says "notify user", follow this procedure. Notifications are NOT a separate skill — they are inline calls made at specific points in helm-go (and helm-merge).

### Step 1: Update status file (always)

Write the event to `_helm/scratch/status.md`. This happens regardless of config — the status file is the most reliable channel.

For blocking events, ensure `blocked: true` and `blocked_reason:` are set (already handled by Post-Failure State above).

For completion events, ensure `phase: ready-to-merge`.

### Step 2: Send notification

Run the `notify.sh` script. It reads `_helm/config.yaml`, detects the platform, and sends a desktop toast (and Slack, when enabled). Best-effort — failures warn on stderr, never block execution.

```bash
bash "$(git rev-parse --show-toplevel)/plugins/helm/scripts/notify.sh" \
  --event "<EVENT>" \
  --branch "$(git branch --show-current)" \
  --detail "<detail>" \
  --urgency "<info|high>"
```

Replace `<EVENT>` with `BLOCKED` or `COMPLETE`, `<detail>` with the reason, and `<urgency>` with `high` (blocking events) or `info` (completion events).

### When to notify

| Call site | Event | Urgency |
|-----------|-------|---------|
| Phase: Implement — step failure after 3 retries | `BLOCKED: Test failure in step N after 3 retries` | High |
| Phase: Resolve — reviewer blocks after max rounds | `BLOCKED: Code reviewer dispute after <max_review_rounds> rounds` | High |
| Phase: Implement — permission/config error | `BLOCKED: Permission/config error (no retries)` | High |
| Phase: Setup — plan stale | `BLOCKED: Plan stale — files changed` | High |
| Completion — all tasks done | `COMPLETE: All tasks done, ready to merge` | Info (toast + status only, skip Slack) |

**Info-level events** (completion) fire toast and status file only — no Slack ping. Check `helm-status` when ready.

---

## Systematic Debugging Protocol

Before retrying any code error, follow this protocol. No guessing. No "I think I know what's wrong."

### Phase 1: Reproduce

Before investigating, reproduce the exact failure.

- If test failure: run the specific failing test, confirm it fails with the same error.
- If build failure: run the build command, confirm the same error.
- Document: exact steps, exact error message, exact location.

If you cannot reproduce after 3 attempts, escalate --- the issue may be environmental.

### Phase 2: Trace backward

Trace from symptom to root cause. Do NOT trace forward from a guess.

1. **Observe the symptom** --- what error, where, what was the code trying to do?
2. **Find the immediate cause** --- what code directly produces the error?
3. **Ask "what called this?"** --- map the call chain backward.
4. **Keep tracing** --- continue asking "what called this?" while reading actual code at each step.
5. **Find the root cause** --- often far from the symptom: initialization, config, data transformation.

### Phase 3: One hypothesis at a time

1. State the hypothesis clearly: "The root cause is X because Y."
2. Make ONE minimal change to test it.
3. Run the reproduction steps. Did it help?
4. If not: form a NEW hypothesis based on what you learned.
5. **After 3 failed hypotheses: STOP.** The problem is likely architectural, not a simple bug. Escalate.

Never change multiple things at once. You can't learn from simultaneous changes.

### Phase 4: Targeted fix

Root cause confirmed. Fix it properly:

1. Write a failing test that captures the root cause (if applicable).
2. Implement a minimal, clean fix.
3. Re-run the exact reproduction steps from Phase 1 --- the fix is not done until the original failure passes.
4. Remove any temporary debug logging.

---

## Failure Classification

When a step fails after exhausting retries, classify before escalating:

### 1. Permission / Config Error
**Signals:** "permission denied", "module not found", missing API key, env var undefined.
**Action:** Notify user immediately. Do NOT retry --- retrying with the same config hits the same error.

### 2. Code Error
**Signals:** Test failure, type error, build failure where the cause is in code written by this task.
**Action:** Already retried 3 times via debugging protocol. Escalate with diagnosis.

### 3. Upstream Dependency Error
**Signals:** Import from a file that doesn't exist yet, API endpoint not available, dependency on another worktree's work that hasn't merged.
**Action:** Block the task. The dependency must be resolved first.

### 4. Review Escalation
**Signals:** Code reviewer has unresolved BLOCKING issues after `max_review_rounds` rounds.
**Action:** Present both sides to user for decision.

---

## Post-Failure State

On any failure that blocks progress:

1. Update `_helm/scratch/status.md` with `blocked: true` and `blocked_reason:`.
2. Move task to `## Blocked` in `kanbans/board.kanban.md` from whatever current column. Validate per `doc/modules/validation.md` (6-column rules).
3. Preserve all state --- do not clean up, do not rollback automatically.
4. Run the **Notification Procedure** (see section above) with the BLOCKED event.
5. Report the blocker to the user.
