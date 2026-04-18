# Code Review Protocol

The code reviewer validates that the diff produced by Thread B's Phase: Implement matches the approved plan and meets quality standards. It is spawned by Thread B's Phase: Review per `implementer-brief.md`.

The code reviewer is **review-only**. It evaluates the diff and writes a review report. It never modifies source files. Thread B (the implementer-orchestrator) reads the review and applies fixes itself per the principle: *the thread that produced the artifact fixes the artifact*. Thread A (`mill-go`) does not resurrect for code fixes — once the plan is approved, Thread A blocks waiting for Thread B and does not edit code.

## Invocation Pattern

Dispatched via `millpy.entrypoints.spawn_reviewer --phase code`. Synchronous from the caller's perspective. The caller is Thread B, not Thread A.

- **Model:** resolved from `review-modules.code.<N>` (where `<N>` is the 1-indexed round number) if present, else from `review-modules.code.default`. See `overview.md#config-resolution` for the resolution rule. Thread B passes the reviewer name to `spawn_reviewer`; the entrypoint resolves the model internally.
- **Max rounds:** default 3, configurable via `-cr N` argument to `mill-go` (passed through to Thread B via the implementer brief) or via `reviews.code` in `_millhouse/config.yaml`. `-cr 0` skips code review entirely.
- The orchestrator (Thread B) passes the approved plan content, the codeguide Overview content (if present), `CONSTRAINTS.md` content (if present), the git diff (`git diff <plan_start_hash>..HEAD`), and the list of file paths touched. The reviewer has these inlined in the prompt and reads no other files except the source files referenced in the diff and any files needed for cross-checking patterns.
- The reviewer's stdout is a single JSON line: `{"verdict": "APPROVE" | "REQUEST_CHANGES", "review_file": "<absolute-path>"}`.

## What the Reviewer Receives

- The approved plan content (inlined in the prompt)
- Codeguide Overview content (if `_codeguide/Overview.md` exists)
- `CONSTRAINTS.md` content (if exists at repo root)
- The diff: `git diff <plan_start_hash>..HEAD`
- The list of file paths touched by the diff

## What the Reviewer Does NOT Receive

- Thread B's commit messages or per-step status updates
- Prior round findings from earlier rounds
- Conversation history from Thread B
- The `.mill/active/<slug>/reviews/` directory (the reviewer is forbidden to read it — see CRITICAL banners below)

## Reviewer Prompt Template

Thread B materializes this prompt into `_millhouse/scratch/code-review-prompt-r<N>.md`, substituting `<DIFF>`, `<PLAN_CONTENT>`, `<OVERVIEW_CONTENT>`, `<CONSTRAINTS_CONTENT>`, `<FILE_PATHS>`, and `<N>` (the current round number, 1-indexed). The materialized file is then passed to `spawn_reviewer` as `--prompt-file`.

---

You are an independent code reviewer. You evaluate the diff and produce a review report. You do **not** modify source files. You have no shared context with the implementing agent — you see only the diff, the plan, and the quality standards.

**CRITICAL: Do NOT commit, push, or run any git commands. You only read files and write the review report.**

**CRITICAL: Do NOT read any files in `.mill/active/<slug>/reviews/`. You must evaluate the diff independently with no knowledge of prior review rounds.**

**CRITICAL: Do NOT edit any source files. The implementer-orchestrator (Thread B) applies fixes based on your review.**

---

**FIRST ACTION — mandatory before anything else:**
Read `_codeguide/Overview.md` if it exists. Use its module table and routing hints to navigate to relevant source files. If it does not exist, proceed without it.

**Context provided:**

1. The approved plan:
   \<PLAN_CONTENT>

2. Codeguide Overview (if available):
   \<OVERVIEW_CONTENT>

3. Repository constraints (if available):
   \<CONSTRAINTS_CONTENT>

4. The diff to review:
   \<DIFF>

5. Files touched by the diff:
   \<FILE_PATHS>

**Evaluate the diff against these criteria:**

- **Plan alignment:** Does the code match the plan? Are there steps in the plan that the diff doesn't implement, or code in the diff that the plan doesn't describe?
- **Design intent:** For each `### Decision:` subsection in the plan's `## Context`, verify the implementation reflects the stated choice and does not silently deviate. Flag deviations as BLOCKING.
- **Correctness:** Bugs, logic errors, off-by-one errors, null/undefined handling?
- **Dead code:** Unused exports, unimported files, unreachable branches?
- **Test thoroughness** (enforce `@mill:testing` rules):
  - Happy-path-only tests → BLOCKING. Error paths and edge cases from the plan's `Key test scenarios` must be covered.
  - Implementation-mirroring tests (testing internal state instead of observable behavior) → BLOCKING.
  - Shallow assertions (`assert result`, `assert result is not None`) → BLOCKING.
  - TDD-marked steps where the diff shows implementation committed without a preceding failing test → BLOCKING.
- **Utility duplication** (BLOCKING): For every new function, helper, or utility in the diff, grep the codebase for existing implementations with similar names or purposes. Use the codeguide Overview to identify which modules to check. If an existing utility covers the same functionality, flag the reimplementation as BLOCKING with a pointer to the existing implementation.
- **Constraint violations** (BLOCKING): Check every constraint in the constraints section. If the diff introduces code that violates any constraint, flag as BLOCKING with the constraint heading and the violating code.
- **Pattern consistency:** Check that new code follows the same patterns as existing code in the same area — naming conventions, error handling style, authentication patterns on endpoints.
- **Codebase consistency:** Does the code follow existing patterns in the codebase?

**Output format:**

Generate the timestamp for the filename via shell: `date -u +"%Y%m%d-%H%M%S"` (see `@mill:cli` timestamp rules — never guess timestamps).

Write the full review report to `.mill/active/<slug>/reviews/<timestamp>-code-review-r<N>.md` (using the shell-generated timestamp and the round number `<N>`).

For each finding: state the file and line(s), severity (**BLOCKING** or **NIT**), the issue, and a suggested fix. End with per-file observations (one sentence per file changed) and verdict: **APPROVE** or **REQUEST_CHANGES**. APPROVE must include per-file observations — a bare "APPROVE" without per-file analysis is invalid.

Return as the final line of your output a single JSON object: `{"verdict": "APPROVE" | "REQUEST_CHANGES", "review_file": "<absolute-path>"}`. No preamble, no additional content. The `spawn_reviewer` entrypoint extracts this JSON line from the `claude -p` result and writes it to its own stdout.

---

## Dispatch Modes

Code-review can run in two dispatch modes, determined by the reviewer recipe's `dispatch:` field in `_millhouse/config.yaml`:

- **`tool-use`** (this file) — The reviewer receives a materialized prompt and has full tool access (Read, Write, Grep, Bash). Used for Claude reviewers where the rate limit does not apply and existing prompt templates already assume tool-use. This file (`code-review.md`) is the template for `dispatch: tool-use` reviewers.

- **`bulk`** (`code-review-bulk.md`) — The reviewer receives all file contents inlined in the prompt and has no tool access. Used for Gemini workers where the Code Assist rate limit (~5 req/min) prohibits per-tool-call API requests. See `plugins/mill/doc/prompts/code-review-bulk.md` for the bulk template.

Reviewer-name resolution happens in `spawn-reviewer.py` via `review-modules.code.<round>|default`. The chosen recipe's `dispatch:` field determines which template is used. Thread B no longer directly references model names for code-review — it passes a reviewer name to `spawn-reviewer.py` which handles dispatch internally.

See `plugins/mill/doc/architecture/reviewer-modules.md` for the full reviewer-module architecture.

## Review Loop

1. Thread B materializes the prompt template into `_millhouse/scratch/code-review-prompt-r<N>.md` and spawns `PYTHONPATH=<scripts-dir> python -m millpy.entrypoints.spawn_reviewer --reviewer-name <name> --prompt-file <prompt-path> --phase code --round <N> --plan-start-hash <plan_start_hash>`. The reviewer name is resolved from `review-modules.code.<N>|default` in `_millhouse/config.yaml`.
2. Reviewer writes findings to `.mill/active/<slug>/reviews/<timestamp>-code-review-r<N>.md`.
3. Reviewer returns a JSON line: `{"verdict": ..., "review_file": ...}`. The script writes this to its own stdout. Thread B parses it.
4. If **APPROVE**: Thread B proceeds to Phase: Finalize. Thread B does **not** read the review file.
5. If **REQUEST_CHANGES**: Thread B invokes the `mill-receiving-review` skill via the Skill tool — this is mandatory before evaluating any finding. Then Thread B reads the review report, applies fixes inline to the affected source files, re-runs full verification (`verify` command from plan frontmatter), writes a fixer report to `.mill/active/<slug>/reviews/<timestamp>-code-fix-r<N>.md` with `## Fixed` and `## Pushed Back` sections, and re-spawns the reviewer with the **updated diff only**. Do NOT pass prior review findings or fixer reports to the reviewer. The reviewer always starts fresh from the updated diff alone, with no context from prior rounds.
6. **Re-verify after fixes.** If full verification fails after the fix phase, treat as a blocked state (same handling as Phase: Test failure).
7. **Non-progress detection.** Before re-spawning, Thread B compares the current fixer report's `## Pushed Back` section against the previous round's. If the pushed-back findings are identical (same finding numbers and descriptions), non-progress is detected: Thread B blocks immediately rather than spending the remaining rounds.
8. Repeat until **APPROVE** or `max_code_review_rounds` exhausted.
9. If unresolved BLOCKING issues remain after all rounds: Thread B blocks with `Code reviewer dispute after <max> rounds — likely design flaw` and notifies. Thread A is informed via the status file when Thread B exits.

The implementation of the loop, the non-progress detection, the receiving-review enforcement, and the round-counter logic live in `plugins/mill/doc/prompts/implementer-brief.md` (Thread B's prompt).
