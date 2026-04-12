# Plan Review Protocol

The plan reviewer validates that the implementation plan written by `mill-go` Phase: Plan is correct, complete, and atomic enough for Thread B to execute. It is spawned by `mill-go` Phase: Plan Review, before Thread B is spawned.

The plan reviewer is **review-only**. It evaluates the plan and writes a review report. It never modifies the plan file. The orchestrator (Thread A / `mill-go`) reads the review and applies fixes itself per the principle: *the thread that produced the artifact fixes the artifact*.

## Invocation Pattern

Blind sub-agent via `plugins/mill/scripts/spawn-agent.ps1 -Role reviewer -PromptFile <prompt> -ProviderName <model>`. Synchronous from the caller's perspective.

- **Model:** resolved from `models.plan-review.<N>` (where `<N>` is the 1-indexed round number) if present, else from `models.plan-review.default`. See `overview.md#config-resolution` for the resolution rule. The orchestrator (mill-go) does the lookup before invoking the script and passes the resolved model name as `-ProviderName`.
- **Max rounds:** default 3, configurable via `-pr N` argument to `mill-go` or via `reviews.plan` in `_millhouse/config.yaml`. `-pr 0` skips plan review entirely.
- The orchestrator passes only the plan file path, task title, and `CONSTRAINTS.md` content (if present) into the prompt. The reviewer reads the plan file and any codebase files independently — no pre-read plan content is injected by the orchestrator. This prevents context bleed from the orchestrator's interpretation and matches the `discussion-review.md` precedent.
- The reviewer's stdout (extracted by `spawn-agent.ps1` from the `claude -p` JSON `result` field) is a single JSON line: `{"verdict": "APPROVE" | "REQUEST_CHANGES", "review_file": "<absolute-path>"}`.

## What the Reviewer Receives

- Plan file path (reads it independently)
- Task title
- `CONSTRAINTS.md` content (if exists — pre-read by orchestrator and inlined)

## What the Reviewer Does NOT Receive

- The orchestrator's interpretation or commentary on the plan
- Prior round findings from earlier rounds
- Conversation history from `mill-go`
- The `_millhouse/task/reviews/` directory (the reviewer is forbidden to read it — see CRITICAL banners below)

## Reviewer Prompt Template

`mill-go` materializes this prompt into `_millhouse/scratch/plan-review-prompt-r<N>.md`, substituting `<PLAN_FILE_PATH>`, `<TASK_TITLE>`, `<CONSTRAINTS_CONTENT>`, and `<N>` (the current round number, 1-indexed). The materialized file is then passed to `spawn-agent.ps1` as `-PromptFile`.

---

You are an independent plan reviewer. You evaluate the plan and produce a review report. You do **not** modify the plan file. You have no shared context with the planning conversation — you see only the plan, the task description, and the codebase.

**CRITICAL: Do NOT commit, push, or run any git commands. You only read files and write the review report.**

**CRITICAL: Do NOT read any files in `_millhouse/task/reviews/`. You must evaluate the plan independently with no knowledge of prior review rounds.**

**CRITICAL: Do NOT edit the plan file or any source files. The orchestrator applies fixes based on your review.**

---

**FIRST ACTION — mandatory before anything else:**
Read `_codeguide/Overview.md` if it exists. Use its module table and routing hints to navigate to relevant source files. If it does not exist, proceed without it.

**Then do the following in order:**

1. Read the task title:
   - Task: \<TASK_TITLE>

2. Read the plan file at `<PLAN_FILE_PATH>`. **The `## Context` section is the authoritative scope** — it reflects the full discussion, not just the original task description. Evaluate against its content, not against the task title alone.

3. Repository constraints (if available):
   \<CONSTRAINTS_CONTENT>

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
- **Atomicity invariant:** Does each step card pass the extraction test from `plan-format.md`? A card that requires reading another step's `## Decisions` for context fails the test.

**Output format:**

Generate the timestamp for the filename via shell: `date -u +"%Y%m%d-%H%M%S"` (see `@mill:cli` timestamp rules — never guess timestamps).

Write the full review report to `_millhouse/task/reviews/<timestamp>-plan-review-r<N>.md` (using the shell-generated timestamp and the round number `<N>`).

For each finding: state the step or section, severity (**BLOCKING** or **NIT**), the issue, and a suggested fix. End with verdict: **APPROVE** or **REQUEST_CHANGES**.

Return as the final line of your output a single JSON object: `{"verdict": "APPROVE" | "REQUEST_CHANGES", "review_file": "<absolute-path>"}`. No preamble, no additional content. The wrapping `spawn-agent.ps1` script extracts this JSON line from the `claude -p` result and writes it to its own stdout.

---

## Review Loop

1. `mill-go` materializes the prompt template into `_millhouse/scratch/plan-review-prompt-r<N>.md` and spawns `spawn-agent.ps1 -Role reviewer -PromptFile <prompt-path> -ProviderName <model>`.
2. Reviewer writes findings to `_millhouse/task/reviews/<timestamp>-plan-review-r<N>.md`.
3. Reviewer returns a JSON line: `{"verdict": ..., "review_file": ...}`. The script writes this to its own stdout. mill-go parses it.
4. If **APPROVE**: mill-go sets `approved: true` in the plan frontmatter, updates `status.md` (`phase: planned`, timeline entry), and proceeds to Phase: Setup. mill-go does **not** read the review file.
5. If **REQUEST_CHANGES**: mill-go reads the review report, invokes the `mill-receiving-review` skill (mandatory), applies fixes inline to the plan file, writes a fixer report to `_millhouse/task/reviews/<timestamp>-plan-fix-r<N>.md` with `## Fixed` and `## Pushed Back` sections, then re-spawns the reviewer with the **updated plan only**. Do NOT pass prior review findings or fixer reports to the reviewer. The reviewer always starts fresh from the updated plan alone, with no context from prior rounds.
6. **Non-progress detection.** Before re-spawning, mill-go compares the current fixer report's `## Pushed Back` section against the previous round's. If the pushed-back findings are identical (same finding numbers and descriptions), non-progress is detected: mill-go blocks immediately rather than spending the remaining rounds. The non-progress signal usually indicates a design dispute that another round will not resolve.
7. Repeat until **APPROVE** or `max_plan_review_rounds` exhausted.
8. If unresolved BLOCKING issues remain after all rounds: mill-go blocks with `Plan review dispute after <max> rounds` and notifies the user. This likely indicates a design flaw rather than something fixable with another review round.

The implementation of the loop, the non-progress detection, and the round-counter logic live in `plugins/mill/skills/mill-go/SKILL.md` Phase: Plan Review.
