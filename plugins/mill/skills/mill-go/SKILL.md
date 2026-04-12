---
name: mill-go
description: Full autonomous execution engine — plan, implement, review, merge.
argument-hint: "[-pr N] [-cr N]"
---

# mill-go

You are a session agent. You write the implementation plan from the discussion file, review it, implement it, run tests, submit your work for independent code review, and merge. You do not inspect your own work; separate reviewer agents do that. You stop the line when something breaks and escalate when you cannot resolve a problem.

Autonomous. Plan, implement, review, merge.

---

## Entry

Read `_millhouse/config.yaml`. If it does not exist, stop --- tell the user to run `mill-setup` first.

Read `_millhouse/scratch/status.md`. Check the `phase:` field from the YAML code block is exactly `discussed` (the completion sentinel confirming `mill-start` finished normally). If `phase:` is missing, not `discussed`, or is a partial value (e.g. `discussing`), stop --- tell the user to complete `mill-start` first.

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
| `-cr N` | `3` | Maximum number of code review rounds. `-cr 0` skips code review entirely (Phase: Review and Phase: Resolve are not executed). |

Parse `-pr` and `-cr` values from the skill invocation arguments. If not provided via CLI, read `reviews.plan` and `reviews.code` from `_millhouse/config.yaml` as defaults (already read at Entry). CLI args override config. If neither is set, default to `3`. Store as `max_plan_review_rounds` and `max_code_review_rounds`.

---

## Resume Protocol

On entry, check if this is a resume (prior work exists):

1. Read the YAML code block in `_millhouse/scratch/status.md` for `phase:`, `plan:`, `current_step:`, and retry counts under `retries:`.

2. **Pre-Setup resume.** Plan and Plan Review phases do not produce commits, so `git log --oneline` is not useful for detecting progress --- use status.md fields exclusively:
   - If `phase: discussed` and no `plan:` field: Phase: Plan (plan not yet written). Re-write the plan from scratch using the discussion file.
   - If `phase: discussed` and `plan:` field exists but plan frontmatter has `approved: false`: Phase: Plan Review (plan written, not yet approved). Re-enter the plan review loop with the existing plan.
   - If `phase: discussed` and `plan:` field exists and plan frontmatter has `approved: true`: plan approved but phase not yet updated → enter Phase: Setup normally.
   - If `phase: planned`: plan approved and phase written, Phase: Setup not yet complete → enter Phase: Setup (skip the `approved: true` check, proceed to setup steps).

3. **Post-Setup resume** (existing git-log-based detection):
   - Check `git log --oneline` for commits matching plan step `Commit:` messages.
   - For each matching commit: mark that step as already done --- skip it.
   - Determine current phase from the `phase:` field in the YAML code block of status.md:
     - `implementing` → Phase: Implement (resume from current_step)
     - `testing` → Phase: Test
     - `reviewing` → Phase: Review
     - `blocked` → report blocker from status.md and stop
   - Continue from the first incomplete step.

Do NOT redo completed work. Do NOT re-run tests for steps that already committed successfully.

---

## Test Baseline

Before implementing any steps (and only if not resuming past this point), capture the test baseline:

1. Run the full test suite (`verify` command from plan frontmatter).
2. Record which tests fail (if any) to `_millhouse/scratch/test-baseline.md`.
3. If all pass: write "All tests pass --- clean baseline."
4. If verify command isn't runnable yet (missing dependencies, not buildable): write "No baseline --- not yet buildable."
5. If verify is `N/A`: check the discussion file's `## Testing Strategy` section. If it specifies that tests should be written or mentions a test approach, there is a contradiction --- the verify command should not be N/A when tests are planned. Report the contradiction to the user and stop until resolved. If Testing Strategy also says no tests, write "No verify command --- skip test baseline."

During implementation, if a test failure matches the baseline (pre-existing), do not count it as a regression. Only new failures trigger retries.

---

## Phases

mill-go proceeds through named phases. Each phase updates the YAML code block in `_millhouse/scratch/status.md` with the current phase name and relevant fields, and inserts timeline entries before the closing ` ``` ` of the timeline text block. On resume, the agent reads the phase from the YAML code block in status.md and continues from there.

### Phase: Plan

0. Read the discussion file for all context: problem, approach, decisions, constraints, technical context, testing strategy, Q&A log, config.

1. **Write the implementation plan.** Generate the timestamp via shell (see `@mill:cli` timestamp rules — never guess timestamps):
   ```bash
   TS=$(date -u +"%Y%m%d-%H%M%S")
   ```
   Use `$TS` for the `started:` frontmatter field.

   Write the plan to `_millhouse/scratch/plan.md` using this format:

   ```markdown
   ---
   verify: <verify command from discussion Config section>
   dev-server: <dev server command from discussion Config section>
   approved: false
   started: <$TS value>
   ---

   # <Task Title>

   ## Context
   Summary of the problem and what was discussed.

   ### Decision: <title>
   **Why:** Reasoning behind the choice.
   **Alternatives rejected:** What else was considered and why not.

   ## Files
   - path/to/file1
   - path/to/file2

   ## Steps

   ### Step 1: <description>
   - **Creates:** `path/to/new/file` (or none)
   - **Modifies:** `path/to/existing/file` (or none)
   - **Requirements:**
     - Requirement 1
     - Requirement 2
   - **Explore:**
     - What to explore and why
   - **TDD:** RED -> GREEN -> REFACTOR (if applicable)
   - **Test approach:** unit / handler-level / browser
   - **Key test scenarios:**
     - Happy: description
     - Error: description
     - Edge: description
   - **Commit:** `type: commit message`
   ```

   **Writing `## Context`:** Copy decisions from the discussion file's `## Decisions` section. Each `### Decision:` subsection must have `**Why:**` and `**Alternatives rejected:**`. These are what reviewers check against.

   Include quality & testing strategy from the discussion file. Each step should touch a small, reviewable scope. Never bundle unrelated file operations into a single step.

   Write the full plan autonomously --- no incremental approval checkpoints.

   Update the YAML code block in status.md: add `plan: _millhouse/scratch/plan.md`.

### Phase: Plan Review (BLOCKING GATE) (round N/max_plan_review_rounds)

**If `max_plan_review_rounds` is `0`:** skip Phase: Plan Review entirely. Set `approved: true` in plan frontmatter and proceed to Phase: Setup.

| Thought that means STOP | Reality |
|---|---|
| "The plan looks good, I'll skip review" | Run the review subagent. Every time. **No exceptions.** |
| "This is a simple change, review isn't needed" | Simple changes have the most unexamined assumptions. Review anyway. |
| "I'll save time and go straight to Setup" | Time saved here is bugs shipped later. Run the gate. |

**Verification:** You MUST have spawned the plan-reviewer agent before proceeding to Phase: Setup. If you have not, go back and run Phase: Plan Review now.

2. **Plan review loop:**

   **Setup:** Ensure `_millhouse/scratch/reviews/` directory exists (`mkdir -p` if not). Initialize `prev_fixer_report_path` to empty (no previous fixer report on first round).

   a. Report to user: **"Plan Review --- round N/&lt;max_plan_review_rounds&gt;"** (where N is the current round number, starting at 1)

   b. Read `CONSTRAINTS.md` from repo root (via `git rev-parse --show-toplevel`) if it exists (pass content to merged agent).

   c. Spawn the **plan review+fix agent** using the Agent tool with the model from `models.plan-review` in `_millhouse/config.yaml`. Pass the following prompt verbatim, substituting `<PLAN_CONTENT>`, `<TASK_TITLE>`, `<CONSTRAINTS_CONTENT>`, `<PLAN_FILE_PATH>`, and `<N>` (the current round number):

      ---
      You are an independent plan reviewer and fixer. You operate in two phases: first review (read-only), then fix (if needed). You have no shared context with the planning conversation --- you see only the plan, the task description, and the codebase.

      **CRITICAL: Do NOT commit, push, or run any git commands. You only read files, write review/fix reports, and edit the plan file. The orchestrator handles all git operations.**

      **CRITICAL: Do NOT read any files in `_millhouse/scratch/reviews/`. You must evaluate the plan independently with no knowledge of prior review rounds.**

      ---

      ## Phase 1: Review (read-only)

      **FIRST ACTION --- mandatory before anything else:**
      Read `_codeguide/Overview.md` if it exists. Use its module table and routing hints to navigate to relevant source files. If it does not exist, proceed without it.

      **Then do the following in order:**

      1. Read the task title:
         - Task: <TASK_TITLE>

      2. Read the plan (the `## Context` section is the authoritative scope — it reflects the full discussion, not just the original task description):
         <PLAN_CONTENT>

      3. Repository constraints (if available):
         <CONSTRAINTS_CONTENT>

      4. Read all source files referenced in the plan's `## Files` section.

      **Evaluate the plan against these criteria:**

      - **Constraint violations** (BLOCKING): Check every constraint in the constraints section. If any plan step would require violating a constraint, flag as BLOCKING with the constraint heading and the problematic step.
      - **Alignment:** Does the plan address all requirements from the task description? Are there requirements in the task that the plan ignores?
      - **Design decision alignment:** For each `### Decision:` subsection in `## Context`, verify the plan's steps faithfully implement the stated choice. Flag decisions that no step addresses, or steps that contradict a stated decision, as BLOCKING.
      - **Completeness:** Are there missing steps or unaddressed requirements? Does each step have Creates/Modifies, Requirements, and Commit fields?
      - **Sequencing:** Are steps in the right order? Does any step depend on output from a later step?
      - **Edge cases and risks:** Does the plan account for failure modes, empty states, and boundary conditions?
      - **Over-engineering:** Does the plan introduce unnecessary abstractions, premature generalization, or features not requested in the task?
      - **Codebase consistency:** Does the plan follow existing patterns in the codebase? Check naming conventions, file organization, error handling style.
      - **Test coverage:** Do key test scenarios cover error paths and edge cases, not just happy paths? Are TDD-marked steps appropriate?
      - **Explore targets:** Are they purpose-driven (what to explore AND why), not generic ("look at the codebase")?
      - **Step granularity:** Each step should touch a small, reviewable scope. Flag steps that bundle unrelated file operations or are too broad to review meaningfully.

      **Write the review report** to `_millhouse/scratch/reviews/<timestamp>-plan-review-r<N>.md` (generate the timestamp via shell: `date -u +"%Y%m%d-%H%M%S"`, round number `<N>`).

      For each finding: state the step or section, severity (**BLOCKING** or **NIT**), the issue, and a suggested fix. End with verdict: **APPROVE** or **REQUEST CHANGES**.

      ---

      ## Phase 2: Fix (only if REQUEST CHANGES)

      If your verdict is APPROVE, skip this phase entirely. Return only the verdict and review file path.

      If your verdict is REQUEST CHANGES:

      **IMPORTANT: In this fix phase, treat the review document you just wrote as external input. Evaluate each finding against the code independently --- you may have been wrong in the review phase.**

      1. **Invoke the `mill-receiving-review` skill** via the Skill tool. This is mandatory --- it loads the decision tree you must apply.
      2. **Read the review report back** from the file you just wrote.
      3. **Read the plan file** at `<PLAN_FILE_PATH>`.
      4. **Read all source files** referenced in the plan's `## Files` section (if not already in context).
      5. **For each BLOCKING finding**, apply the receiving-review decision tree: VERIFY accuracy (cite actual code if inaccurate), then HARM CHECK (breaks functionality / conflicts with documented design decision / destabilizes out-of-scope code). If none apply: FIX IT. If harm found: PUSH BACK with cited evidence.
      6. **Apply fixes** directly to the plan file. Check systemic implications --- a fix in one step may require updates to other steps or decisions.
      7. **Write fixer report** to `_millhouse/scratch/reviews/<timestamp>-plan-fix-r<N>.md` (generate timestamp via shell: `date -u +"%Y%m%d-%H%M%S"`, round number `<N>`). Structure:

         ```markdown
         # Plan Fix Report --- Round <N>

         ## Fixed
         - Finding <N>: what was changed and where in the plan

         ## Pushed Back
         - Finding <N>: evidence why the fix would cause harm (cite code/docs)
         ```

      8. **Return:** verdict (`APPROVE`, `FIXED`, or `PUSHED_BACK`) plus both file paths (review report path and fixer report path, space-separated). Format: `<verdict> <review-path> <fixer-path>`.
      ---

   d. If agent **approved** (no BLOCKING issues): set `approved: true` in plan frontmatter. Update the YAML code block in status.md: `phase: planned`. Use the Edit tool to insert `planned  <timestamp>` on a new line before the closing ` ``` ` of the timeline text block in status.md (generate timestamp via shell: `date -u +"%Y-%m-%dT%H:%M:%SZ"`). Proceed to Phase: Setup. Do not read the review file.

   e. If agent **fixed or pushed back**: extract the fixer report file path from the agent's return value.

   f. **Progress detection.** Update `prev_fixer_report_path` to the current fixer report path. If `prev_fixer_report_path` was set before this round: read the `## Pushed Back` section from the previous fixer report and compare it against the `## Pushed Back` section from the current fixer report. If the pushed-back findings are identical (same finding numbers and descriptions), non-progress is detected: update the YAML code block in `_millhouse/scratch/status.md` with `blocked: true`, `blocked_reason: Plan review non-progress — agent pushed back identical findings in consecutive rounds`, `phase: blocked`. Use the Edit tool to insert `blocked  <timestamp>` before the closing ` ``` ` of the timeline text block. Run the **Notification Procedure** with `BLOCKED: Plan review non-progress after consecutive rounds`. Escalate to user immediately rather than spending remaining rounds.

   g. Re-spawn the review+fix agent with the **updated plan content only**. Do NOT pass the fixer report path to the agent. The agent always starts fresh from the updated plan alone, with no context from prior rounds. Report: **"Plan Review --- round N/&lt;max_plan_review_rounds&gt;"**

   h. Max `max_plan_review_rounds` rounds. If unresolved BLOCKING issues remain after all rounds: this likely indicates a design flaw rather than something fixable with another review round. Update the YAML code block in status.md with `blocked: true`, `blocked_reason: Plan review dispute after <max_plan_review_rounds> rounds`, `phase: blocked`. Use the Edit tool to insert `blocked  <timestamp>` before the closing ` ``` ` of the timeline text block. Run the **Notification Procedure** with `BLOCKED: Plan review dispute after <max_plan_review_rounds> rounds`. Present remaining BLOCKING issues to user for decision.

### Phase: Setup

3. Record `PLAN_START_HASH=$(git rev-parse HEAD)`. Store in the YAML code block of `_millhouse/scratch/status.md` as `plan_start_hash:`. On resume, read from the YAML code block in status.md instead of re-computing.

4. Read plan (path from the YAML code block in `_millhouse/scratch/status.md` `plan:` field). Read all files listed in `## Files`.

5. **Staleness check.** Run `git log --since=<started> -- <file1> <file2> ...` using the `started:` timestamp from plan frontmatter and files from `## Files`.
   - No changes: proceed.
   - Minor changes (formatting, comments, unrelated areas): log warning in status.md, proceed.
   - Major changes (files restructured, APIs changed, interfaces modified): halt. Plan-stale revert:
     1. Resolve parent worktree path via `git worktree list --porcelain` or the `parent:` field from the YAML code block in `_millhouse/scratch/status.md`.
     2. Remove the `[phase]` marker from the task's heading in the parent's `tasks.md`. Resolve the parent's project root by computing the project subdirectory offset (working directory minus git root) and applying it to the parent worktree path. Stage, commit, and push `tasks.md` from the parent worktree.
     3. Update the YAML code block in status.md with `blocked: true`, `blocked_reason: Plan stale --- files changed since plan was written`, `phase: blocked`. Use the Edit tool to insert `blocked  <timestamp>` before the closing ` ``` ` of the timeline text block. Run the **Notification Procedure** with `BLOCKED: Plan stale — files changed`. Tell the user to re-run `mill-start`.

6. **Explore.** Read code following each step's `Explore:` targets. If `_codeguide/Overview.md` exists: read it and use the navigation pattern (Overview -> module doc -> Source section -> code).

7. **Read constraints.** Resolve repo root: `git rev-parse --show-toplevel`. Read `CONSTRAINTS.md` from repo root if it exists. These are hard invariants — never write code that violates them. If the file does not exist, proceed without it.

8. **Move to Implementing.** Update the YAML code block in `_millhouse/scratch/status.md`:
   ```
   phase: implementing
   current_step: 1
   ```
   Use the Edit tool to insert `implementing  <timestamp>` on a new line before the closing ` ``` ` of the timeline text block in status.md (generate timestamp via shell: `date -u +"%Y-%m-%dT%H:%M:%SZ"`).

   **Update tasks.md phase marker.** Resolve the parent worktree path via `git worktree list --porcelain`. Compute the parent's project root by applying the project subdirectory offset (working directory minus git root) to the parent worktree path. In the parent's `tasks.md`, update the task's heading from `## [discussing] <Task Title>` (or `## [planned] <Task Title>`) to `## [implementing] <Task Title>`. Stage, commit, and push `tasks.md` from the parent worktree. If running in-place (main worktree), use the working directory directly.

### Phase: Implement

9. **For each step in the plan:**

   a. Update the YAML code block in `_millhouse/scratch/status.md` with current step number and name:
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
      2. Track retry count in the YAML code block of `_millhouse/scratch/status.md` under `retries:` as `step_<N>: <count>`.
      3. Max 3 retries per step.
      4. After 3 retries: classify the failure and route:
         - **Code error** that you cannot fix: update the YAML code block in status.md with `blocked: true`, `blocked_reason:`, `phase: blocked`. Use the Edit tool to insert `blocked  <timestamp>` before the closing ` ``` ` of the timeline text block. Stop.
         - **Permission/config error**: notify user immediately (no retries were appropriate). Update the YAML code block in status.md with `blocked: true`, `blocked_reason:`, `phase: blocked`. Use the Edit tool to insert `blocked  <timestamp>` before the closing ` ``` ` of the timeline text block. Stop.
         - **Upstream dependency error** (import from non-existent file, API not available): update the YAML code block in status.md with `blocked: true`, `blocked_reason:`, `phase: blocked`. Use the Edit tool to insert `blocked  <timestamp>` before the closing ` ``` ` of the timeline text block. Stop.

   f. **Commit and push after each successful step** using the step's `Commit:` message:
      - Stage files individually: `git add file1 file2` --- never `git add .` or `git add -A`.
      - Commit: `git commit -m "<commit message from step>"`
      - Push: `git push`
      - This enables resume on crash.

   On any block (after 3 retries, permission error, upstream dependency): after updating status.md and timeline, run the **Notification Procedure** with the appropriate BLOCKED event.

### Phase: Test

10. Update the YAML code block in `_millhouse/scratch/status.md`:
    ```
    phase: testing
    ```
    Use the Edit tool to insert `testing  <timestamp>` on a new line before the closing ` ``` ` of the timeline text block in status.md (generate timestamp via shell: `date -u +"%Y-%m-%dT%H:%M:%SZ"`).

    **Update tasks.md phase marker.** Resolve the parent's project root (parent worktree path + project subdirectory offset, or working directory if in-place). Update the task's heading in `tasks.md` to `## [testing] <Task Title>`. Stage, commit, and push from the parent worktree.

    **Full verification.** Run the complete verify command from plan frontmatter (lint, type-check, build, test --- whatever the command includes).
    - All tests must pass --- not just tests related to this task.
    - Compare failures against `_millhouse/scratch/test-baseline.md` to distinguish pre-existing failures from new regressions.
    - If new failures: debug and fix using the Systematic Debugging Protocol. Max 3 retries for the full verification. If unresolved: update the YAML code block in status.md with `blocked: true`, `blocked_reason:`, `phase: blocked`. Use the Edit tool to insert `blocked  <timestamp>` before the closing ` ``` ` of the timeline text block. Run Notification Procedure, stop.

    **If verify is `N/A`:** check the discussion file's `## Testing Strategy` section. If it specifies tests, there is a contradiction --- stop and report to user. Otherwise skip verification and proceed directly.

    **If `max_code_review_rounds` is `0`:** skip Phase: Review entirely. Proceed directly to Phase: Finalize.

### Phase: Review (round N/max_code_review_rounds)

11. Update the YAML code block in `_millhouse/scratch/status.md`:
    ```
    phase: reviewing
    ```
    Use the Edit tool to insert `reviewing  <timestamp>` on a new line before the closing ` ``` ` of the timeline text block in status.md (generate timestamp via shell: `date -u +"%Y-%m-%dT%H:%M:%SZ"`).

    **Update tasks.md phase marker.** Resolve the parent's project root (parent worktree path + project subdirectory offset, or working directory if in-place). Update the task's heading in `tasks.md` to `## [reviewing] <Task Title>`. Stage, commit, and push from the parent worktree.

    **Setup:** Ensure `_millhouse/scratch/reviews/` directory exists (`mkdir -p` if not). Initialize `prev_fixer_report_path` to empty (no previous fixer report on first round).

12. **Code review loop:**

    a. Report to user: **"Review --- round N/&lt;max_code_review_rounds&gt;"** (where N is the current round number, starting at 1)

    b. Compute the diff: `git diff <plan_start_hash>..HEAD`

    c. Read `_codeguide/Overview.md` if it exists (pass content to agent). Read `CONSTRAINTS.md` from repo root (via `git rev-parse --show-toplevel`) if it exists (pass content to agent).

    d. Spawn the **code review+fix agent** using the Agent tool with the model from `models.code-review` in `_millhouse/config.yaml`. Pass the following prompt verbatim, substituting `<DIFF>`, `<PLAN_CONTENT>`, `<OVERVIEW_CONTENT>`, `<CONSTRAINTS_CONTENT>`, `<FILE_PATHS>`, and `<N>`:

       ---
       You are an independent code reviewer and fixer. You operate in two phases: first review (read-only), then fix (if needed). You have no shared context with the implementing agent --- you see only the diff, the plan, and the quality standards.

       **CRITICAL: Do NOT commit, push, or run any git commands. You only read files, write review/fix reports, and edit source files. The orchestrator handles all git operations.**

       **CRITICAL: Do NOT read any files in `_millhouse/scratch/reviews/`. You must evaluate the diff independently with no knowledge of prior review rounds.**

       ---

       ## Phase 1: Review (read-only)

       **FIRST ACTION --- mandatory before anything else:**
       Read `_codeguide/Overview.md` if it exists. Use its module table and routing hints to navigate to relevant source files. If it does not exist, proceed without it.

       **Context provided:**

       1. The approved plan:
       <PLAN_CONTENT>

       2. Codeguide Overview (if available):
       <OVERVIEW_CONTENT>

       3. Repository constraints (if available):
       <CONSTRAINTS_CONTENT>

       4. The diff to review:
       <DIFF>

       **Evaluate the diff against these criteria:**

       - **Plan alignment:** Does the code match the plan? Are there steps in the plan that the diff doesn't implement, or code in the diff that the plan doesn't describe?
       - **Design intent:** For each `### Decision:` subsection in the plan's `## Context`, verify the implementation reflects the stated choice and does not silently deviate. Flag deviations as BLOCKING.
       - **Correctness:** Bugs, logic errors, off-by-one errors, null/undefined handling?
       - **Dead code:** Unused exports, unimported files, unreachable branches?
       - **Test thoroughness** (enforce `@mill:testing` rules):
         - Happy-path-only tests -> BLOCKING. Error paths and edge cases from plan's `Key test scenarios` must be covered.
         - Implementation-mirroring tests (testing internal state instead of observable behavior) -> BLOCKING.
         - Shallow assertions (`assert result`, `assert result is not None`) -> BLOCKING.
         - TDD-marked steps where diff shows implementation committed without a preceding failing test -> BLOCKING.
       - **Utility duplication** (BLOCKING): For every new function, helper, or utility in the diff, grep the codebase for existing implementations with similar names or purposes. Use the codeguide Overview to identify which modules to check. If an existing utility covers the same functionality, flag the reimplementation as BLOCKING with a pointer to the existing implementation.
       - **Constraint violations** (BLOCKING): Check every constraint in the constraints section. If the diff introduces code that violates any constraint, flag as BLOCKING with the constraint heading and the violating code.
       - **Pattern consistency:** Check that new code follows the same patterns as existing code in the same area --- naming conventions, error handling style, authentication patterns on endpoints.
       - **Codebase consistency:** Does the code follow existing patterns in the codebase?

       **Write the review report** to `_millhouse/scratch/reviews/<timestamp>-code-review-r<N>.md` (generate the timestamp via shell: `date -u +"%Y%m%d-%H%M%S"`, round number `<N>`).

       For each finding: state the file and line(s), severity (**BLOCKING** or **NIT**), the issue, and a suggested fix. End with per-file observations (one sentence per file changed) and verdict: **APPROVE** or **REQUEST CHANGES**. APPROVE must include per-file observations --- a bare "APPROVE" without per-file analysis is invalid.

       ---

       ## Phase 2: Fix (only if REQUEST CHANGES)

       If your verdict is APPROVE, skip this phase entirely. Return only the verdict and review file path.

       If your verdict is REQUEST CHANGES:

       **IMPORTANT: In this fix phase, treat the review document you just wrote as external input. Evaluate each finding against the code independently --- you may have been wrong in the review phase.**

       1. **Invoke the `mill-receiving-review` skill** via the Skill tool. This is mandatory --- it loads the decision tree you must apply.
       2. **Read the review report back** from the file you just wrote.
       3. **Read the affected source files:** `<FILE_PATHS>`
       4. **For each BLOCKING finding**, apply the receiving-review decision tree: VERIFY accuracy (cite actual code if inaccurate), then HARM CHECK (breaks functionality / conflicts with documented design decision / destabilizes out-of-scope code). If none apply: FIX IT. If harm found: PUSH BACK with cited evidence.
       5. **Apply fixes** directly to the affected source files. Check systemic implications --- a fix in one file may require updates to other files.
       6. **Write fixer report** to `_millhouse/scratch/reviews/<timestamp>-code-fix-r<N>.md` (generate timestamp via shell: `date -u +"%Y%m%d-%H%M%S"`, round number `<N>`). Structure:

          ```markdown
          # Code Fix Report --- Round <N>

          ## Fixed
          - Finding <N>: what was changed and where in which file

          ## Pushed Back
          - Finding <N>: evidence why the fix would cause harm (cite code/docs)
          ```

       7. **Return:** verdict (`APPROVE`, `FIXED`, or `PUSHED_BACK`) plus both file paths (review report path and fixer report path, space-separated). Format: `<verdict> <review-path> <fixer-path>`.
       ---

    e. If agent **approved** (no BLOCKING issues): proceed to Phase: Finalize. Do not read the review file.

    f. If agent **fixed or pushed back**: extract the fixer report file path from the agent's return value.

    g. **Progress detection.** Update `prev_fixer_report_path` to the current fixer report path. If `prev_fixer_report_path` was set before this round: read the `## Pushed Back` section from the previous fixer report and compare it against the `## Pushed Back` section from the current fixer report. If the pushed-back findings are identical (same finding numbers and descriptions), non-progress is detected: update the YAML code block in `_millhouse/scratch/status.md` with `blocked: true`, `blocked_reason: Review non-progress — agent pushed back identical findings in consecutive rounds`, `phase: blocked`. Use the Edit tool to insert `blocked  <timestamp>` before the closing ` ``` ` of the timeline text block. Run the **Notification Procedure** with `BLOCKED: Review non-progress after consecutive rounds`. Escalate to user immediately rather than spending remaining rounds.

    h. **Re-verify.** Re-run full verification (the verify command from plan frontmatter). If verification fails after the fix phase, treat as a blocked state (same as Phase: Test failure handling).

    i. Re-spawn the review+fix agent with the **updated diff only** (`git diff <plan_start_hash>..HEAD`). Do NOT pass the fixer report path to the agent. The agent always starts fresh from the updated diff alone, with no context from prior rounds. Report: **"Review --- round N/&lt;max_code_review_rounds&gt;"**

    j. Max `max_code_review_rounds` rounds. If unresolved BLOCKING issues after all rounds: this likely indicates a design flaw rather than something fixable with another review round. Escalate to user. Update the YAML code block in status.md with `blocked: true`, `blocked_reason: Review dispute after <max_code_review_rounds> rounds — likely design flaw`, `phase: blocked`. Use the Edit tool to insert `blocked  <timestamp>` before the closing ` ``` ` of the timeline text block. Run the **Notification Procedure** with `BLOCKED: Code reviewer dispute after <max_code_review_rounds> rounds`. Present remaining BLOCKING issues to user for decision.

### Phase: Finalize

Phase: Finalize is not resumable at the step level; on crash-resume, mill-go re-enters Phase: Finalize from the beginning. mill-merge's idempotency via its checkpoint branch ensures the merge is not duplicated.

20. **Codeguide update.** If `_codeguide/Overview.md` exists, invoke the `mill:codeguide-update` skill (no arguments --- it defaults to the current git diff).

21. **Post-review commit.** If any files changed during review fixes or codeguide update:
    - Stage files individually: `git add file1 file2` --- never `git add .` or `git add -A`.
    - Commit: `chore: post-review cleanup for <task-title>`
    - Push: `git push`

22. **Update the YAML code block in status.md:**
    ```
    phase: complete
    ```
    Use the Edit tool to insert `complete  <timestamp>` on a new line before the closing ` ``` ` of the timeline text block in status.md (generate timestamp via shell: `date -u +"%Y-%m-%dT%H:%M:%SZ"`).

23. **Auto-merge.** First, read `git.auto-merge` from `_millhouse/config.yaml` (already read at Entry). If `auto-merge` is `false`, skip mill-merge entirely: run the **Notification Procedure** with `COMPLETE: Task done, auto-merge disabled` (info-level --- toast + status only, skip Slack). Report: "Execution complete. Auto-merge disabled --- run `/mill-merge` when ready." Then stop (do not proceed to the child/in-place merge logic below).

    If `auto-merge` is `true` (or not set), check whether mill-go is running in a child worktree or in-place on the main worktree. Detect using `git worktree list --porcelain` — if the current path is the first/main entry, it is in-place; otherwise it is a child worktree.
    - **Child worktree:** invoke `mill-merge` via the Skill tool. If mill-merge fails (conflicts, etc.): update the YAML code block in status.md with `blocked: true`, `blocked_reason: Merge failed`. Run the **Notification Procedure** with `BLOCKED: Merge failed`. Report to user and stop.
    - **In-place (main worktree):** skip mill-merge. Run the **Notification Procedure** with `COMPLETE: All tasks done, ready to merge` (info-level). Report: "In-place execution complete. Task done."

---

## Completion

After successful auto-merge in a child worktree: mill-merge handles its own notification and status update (`phase: complete`). mill-go does not send a duplicate notification.

For in-place runs: mill-go sets `phase: complete` and sends the completion notification itself (step 23).

---

## Stops When

- All tasks complete -> completion flow
- Test failure after 3 retries -> block, notify user
- Plan reviewer blocks after `max_plan_review_rounds` rounds -> block, notify user
- Code reviewer blocks after `max_code_review_rounds` rounds -> block, notify user
- Permission/config error -> block, notify user immediately (no retries)
- Plan staleness (major changes to listed files) -> block, tell user to re-run mill-start
- Merge failure -> block, notify user

---

## Board Updates

tasks.md changes require commit and push (tasks.md is git-tracked). When running from a child worktree, resolve the parent's project root by computing the project subdirectory offset (working directory minus git root) and applying it to the parent worktree path from `git worktree list --porcelain`. Modify the parent's `tasks.md` at that project root.

Phase transitions are tracked via `phase:` in the YAML code block of `_millhouse/scratch/status.md` and the `## Timeline` section (entries inserted before the closing ` ``` ` of the text fence). See `doc/modules/discussion-format.md` for the status.md schema and timeline format.

- Phase transitions → update `[phase]` marker in parent's `tasks.md`, commit and push
- Plan stale → remove `[phase]` marker from task in parent's `tasks.md`, commit and push

---

## Notification Procedure

When the skill says "notify user", follow this procedure. Notifications are NOT a separate skill — they are inline calls made at specific points in mill-go (and mill-merge).

### Step 1: Update status file (always)

Write the event to the YAML code block in `_millhouse/scratch/status.md`. This happens regardless of config — the status file is the most reliable channel.

For blocking events, ensure `blocked: true` and `blocked_reason:` are set (already handled by Post-Failure State above).

For completion events, ensure `phase: complete`.

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

### When to notify

| Call site | Event | Urgency |
|-----------|-------|---------|
| Phase: Plan Review — non-progress after consecutive fixer rounds | `BLOCKED: Plan review non-progress` | High |
| Phase: Plan Review — dispute after max rounds | `BLOCKED: Plan review dispute` | High |
| Phase: Implement — step failure after 3 retries | `BLOCKED: Test failure in step N after 3 retries` | High |
| Phase: Resolve — reviewer blocks after max rounds | `BLOCKED: Code reviewer dispute after <max_code_review_rounds> rounds` | High |
| Phase: Resolve — non-progress after consecutive fixer rounds | `BLOCKED: Review non-progress after consecutive fixer rounds` | High |
| Phase: Implement — permission/config error | `BLOCKED: Permission/config error (no retries)` | High |
| Phase: Setup — plan stale | `BLOCKED: Plan stale — files changed` | High |
| Phase: Finalize — merge failure | `BLOCKED: Merge failed` | High |
| Completion — in-place run complete | `COMPLETE: Task done` | Info (toast + status only, skip Slack) |

**Info-level events** (completion) fire toast and status file only — no Slack ping. Check `mill-status` when ready.

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
**Signals:** Plan or code reviewer has unresolved BLOCKING issues after max rounds.
**Action:** Present both sides to user for decision.

---

## Post-Failure State

On any failure that blocks progress:

1. Update the YAML code block in `_millhouse/scratch/status.md` with `blocked: true`, `blocked_reason:`, and `phase: blocked`. Use the Edit tool to insert `blocked  <timestamp>` before the closing ` ``` ` of the timeline text block.
2. Preserve all state --- do not clean up, do not rollback automatically.
3. Run the **Notification Procedure** (see section above) with the BLOCKED event.
4. Report the blocker to the user.
