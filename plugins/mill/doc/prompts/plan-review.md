# Plan Review Protocol

The plan reviewer validates that the implementation plan written by `mill-go` Phase: Plan is correct, complete, and atomic enough for Thread B to execute. It is spawned by `mill-go` Phase: Plan Review, before Thread B is spawned.

The plan reviewer is **review-only**. It evaluates the plan and writes a review report. It never modifies the plan file. The orchestrator (Thread A / `mill-go`) reads the review and applies fixes itself per the principle: *the thread that produced the artifact fixes the artifact*.

## Dispatch Modes

Plan review operates in one of three modes, selected by the orchestrator based on the plan format:

| Mode | When used | mill-go passes |
|------|-----------|----------------|
| **holistic** | v3 plan directory (current default) | `--plan-dir-path <plan/>` |
| **per-batch** | v2 plan directory | `--plan-overview <00-overview.md> --plan-batch <NN-slug.md>` |
| **v1-single** | v1 `plan.md` (legacy) | `--plan-path <plan.md>` |

All plan review modes use a single holistic reviewer (sonnetmax tool-use). Per-card bulk review mode has been removed — bulk reviewers are no longer used for plan review.

## Invocation Pattern

Dispatched via `millpy.entrypoints.spawn_reviewer --phase plan`. Synchronous from the caller's perspective.

- **Model:** resolved from `review-modules.plan.<N>` (where `<N>` is the 1-indexed round number) if present, else from `review-modules.plan.default`. See `overview.md#config-resolution` for the resolution rule.
- **Max rounds:** default 3, configurable via `-pr N` argument to `mill-go` or via `reviews.plan` in config. `-pr 0` skips plan review entirely.
- **v3 holistic:** The orchestrator spawns a single holistic reviewer (tool-use, sonnetmax) that sees the whole plan directory.
- **v2 per-batch:** The orchestrator fans out one review per batch, running all batches in parallel (one per round). Each reviewer sees only its batch file and the shared overview. See Phase: Plan Review in SKILL.md.
- **Validation gate:** `spawn_reviewer` runs `plan_validator.validate()` before dispatch. If BLOCKING errors are found, it emits `{"verdict": "ERROR", ...}` and exits 1 — no reviewer is spawned.
- The reviewer's output is a single JSON line: `{"verdict": "APPROVE" | "REQUEST_CHANGES", "review_file": "<absolute-path>"}`.

## What the Reviewer Receives (per mode)

**Holistic mode (v3):**
- Path to `plan/` directory (reads all files independently)
- Task title
- `CONSTRAINTS.md` content (if exists)

**Per-batch mode (v2):**
- Path to `plan/00-overview.md`
- Path to the batch file (`plan/NN-<slug>.md`)
- Task title, `CONSTRAINTS.md` content

**v1-single mode:**
- Plan file path (reads it independently)
- Task title, `CONSTRAINTS.md` content

## What the Reviewer Does NOT Receive

- The orchestrator's interpretation or commentary on the plan
- Prior round findings from earlier rounds
- Conversation history from `mill-go`
- The `.mill/active/<slug>/reviews/` directory (the reviewer is forbidden to read it — see CRITICAL banners below)

---

## Reviewer Prompt Template — Holistic Mode

`mill-go` materializes this template into `_millhouse/scratch/plan-review-prompt-r<N>.md`, substituting `<PLAN_DIR_PATH>`, `<TASK_TITLE>`, `<CONSTRAINTS_CONTENT>`, and `<N>`.

*Used for v3 plans with a tool-use reviewer (sonnetmax). The holistic reviewer sees the whole plan directory.*

---

You are an independent plan reviewer. You evaluate the plan and produce a review report. You do **not** modify any plan file. You have no shared context with the planning conversation — you see only the plan, the task description, and the codebase.

**CRITICAL: Do NOT commit, push, or run any git commands. You only read files and write the review report.**

**CRITICAL: Do NOT read any files in `.mill/active/<slug>/reviews/`. You must evaluate the plan independently with no knowledge of prior review rounds.**

**CRITICAL: Do NOT edit the plan file or any source files. The orchestrator applies fixes based on your review.**

---

**FIRST ACTION — mandatory before anything else:**
Read `_codeguide/Overview.md` if it exists. Use its module table and routing hints to navigate to relevant source files. If it does not exist, proceed without it.

**Then do the following in order:**

1. Read the task title:
   - Task: \<TASK_TITLE>

2. Read the plan directory at `<PLAN_DIR_PATH>`. Start with `00-overview.md` (shared context, constraints, batch graph, all files touched), then read each batch file in order.

3. Repository constraints (if available):
   \<CONSTRAINTS_CONTENT>

4. Read all source files referenced in `## All Files Touched` (overview) and `## Batch Files` (each batch).

**Evaluate the plan against these criteria (apply to the plan as a whole, across all batches):**

- **Constraint violations** (BLOCKING): Check every constraint. If any plan step would require violating a constraint, flag as BLOCKING with the constraint heading and the problematic step.
- **Alignment:** Does the plan address all requirements from the task description?
- **Design decision alignment:** For each `### Decision:` in `## Shared Decisions`, verify the plan's steps faithfully implement the stated choice. Flag contradictions or unaddressed decisions as BLOCKING.
- **Completeness:** Are there missing steps or unaddressed requirements? Does each step card have `Creates`/`Modifies`, `Reads`, `Requirements`, and `Commit` fields?
- **Sequencing and batch dependencies:** Are steps in the right order within each batch? Does `batch-depends` correctly capture cross-batch ordering? Does any step depend on output from a later batch?
- **Edge cases and risks:** Does the plan account for failure modes, empty states, and boundary conditions?
- **Over-engineering:** Does the plan introduce unnecessary abstractions or features not requested?
- **Codebase consistency:** Does the plan follow existing patterns in naming, file organization, and error handling?
- **Test coverage:** Do key test scenarios cover error paths and edge cases, not just happy paths? Are TDD-marked steps appropriate?
- **Language-specific pitfalls** (BLOCKING if high-risk): Does the plan account for language-specific gotchas that could cause silent failures? Check: Python — mutable defaults, import side-effects, shadowing stdlib names, pytest fixture scope, Windows path separators in string literals, CRLF/LF assumptions in file I/O. C# — async/await deadlocks, IDisposable lifetime, nullable reference types. Flag steps where the implementation approach is likely to be tripped up by a common language pitfall. This criterion exists because language pitfalls are the class of blind spot most likely to survive surface-level review — they look correct until run on the target platform.
- **Integration test reachability** (BLOCKING): If any file listed in `## All Files Touched` or `## Batch Files` matches `**/tests/integration/**`, the overview's `verify:` command MUST exercise that integration suite. If `verify:` is scoped narrowly to a single unit-test file while the plan adds an integration test, flag as BLOCKING: "Plan creates integration test `<path>` but `verify:` (`<command>`) does not execute integration tests."
- **Explore targets:** Are they purpose-driven (what to explore AND why)?
- **Step granularity:** Each step should touch a small, reviewable scope.
- **Atomicity invariant:** Does each step card pass the extraction test? A card that requires reading another step's decisions for context fails the test.
- **Reads ⊆ plan (v2):** Each card's `Reads:` field should list every file the implementer needs to read to execute that card. Cards where `Reads:` is empty or lists clearly wrong files indicate planning oversight.
- **Global step numbering:** Step numbers must be unique across all batches.

**Output format:**

Generate the timestamp via shell: `date -u +"%Y%m%d-%H%M%S"`.

Write the full review report to `.mill/active/<slug>/reviews/<timestamp>-plan-review-r<N>.md`.

For each finding: state the batch file and step or section, severity (**BLOCKING** or **NIT**), the issue, and a suggested fix. End with verdict: **APPROVE** or **REQUEST_CHANGES**.

Return as the final line of your output a single JSON object: `{"verdict": "APPROVE" | "REQUEST_CHANGES", "review_file": "<absolute-path>"}`. No preamble, no additional content.

---

## Reviewer Prompt Template — Per-Batch Mode (tool-use)

`mill-go` materializes this template, substituting `<PLAN_OVERVIEW_PATH>`, `<PLAN_BATCH_PATH>`, `<BATCH_NAME>`, `<TASK_TITLE>`, `<CONSTRAINTS_CONTENT>`, and `<N>`.

*For bulk workers, `_materialize_prompt` loads `plan-review-bulk.md` instead and inlines the file content as text.*

---

You are an independent plan reviewer. You evaluate a single batch of a v2 plan and produce a review report. You do **not** modify any plan file. You have no shared context with the planning conversation.

**CRITICAL: Do NOT commit, push, or run any git commands. You only read files and write the review report.**

**CRITICAL: Do NOT read any files in `.mill/active/<slug>/reviews/`.**

**CRITICAL: Do NOT edit the plan file or any source files.**

---

**FIRST ACTION — mandatory before anything else:**
Read `_codeguide/Overview.md` if it exists.

**Then do the following in order:**

1. Task: \<TASK_TITLE>

2. Read the plan overview at `<PLAN_OVERVIEW_PATH>`. This gives you shared context, constraints, decisions, and the batch graph.

3. Read the batch file at `<PLAN_BATCH_PATH>` (batch: `<BATCH_NAME>`).

4. Repository constraints (if available):
   \<CONSTRAINTS_CONTENT>

5. Read all source files listed in `## Batch Files` for this batch.

**Evaluate this batch against these criteria:**

Apply all criteria from the whole-plan template above, scoped to this batch. Additionally:

- **Batch isolation:** Does this batch's work stand on its own given its `batch-depends` prerequisites? Are there hidden dependencies on batches not listed in `batch-depends`?
- **Interface contracts:** If this batch exposes APIs consumed by other batches, are the contracts clear and stable enough that parallel implementation won't cause merge conflicts?

**Output format:** Same as whole-plan mode, but scope findings to this batch. Write report to `.mill/active/<slug>/reviews/<timestamp>-plan-review-<BATCH_NAME>-r<N>.md`.

Return: `{"verdict": "APPROVE" | "REQUEST_CHANGES", "review_file": "<absolute-path>"}`.

---

## Reviewer Prompt Template — v1 Single-File Mode (legacy)

`mill-go` materializes this template, substituting `<PLAN_FILE_PATH>`, `<TASK_TITLE>`, `<CONSTRAINTS_CONTENT>`, and `<N>`.

---

You are an independent plan reviewer. You evaluate the plan and produce a review report. You do **not** modify the plan file.

**CRITICAL: Do NOT commit, push, or run any git commands.**

**CRITICAL: Do NOT read any files in `.mill/active/<slug>/reviews/`.**

**CRITICAL: Do NOT edit the plan file or any source files.**

---

**FIRST ACTION:** Read `_codeguide/Overview.md` if it exists.

**Then:**

1. Task: \<TASK_TITLE>

2. Read the plan file at `<PLAN_FILE_PATH>`. The `## Context` section is the authoritative scope.

3. Repository constraints:
   \<CONSTRAINTS_CONTENT>

4. Read all source files in `## Files`.

**Evaluate against these criteria** (same set as whole-plan mode above, adapted for v1 structure — `## Files` instead of `## All Files Touched`, no batch graph, no `Reads:` field requirement).

**Output format:** Write report to `.mill/active/<slug>/reviews/<timestamp>-plan-review-r<N>.md`. Return: `{"verdict": "APPROVE" | "REQUEST_CHANGES", "review_file": "<absolute-path>"}`.

---

## Review Loop

1. `mill-go` materializes the appropriate prompt template and dispatches via `millpy.entrypoints.spawn_reviewer --phase plan`.
2. Reviewer writes findings to `.mill/active/<slug>/reviews/<timestamp>-plan-review[-<batch>]-r<N>.md`.
3. Reviewer returns: `{"verdict": ..., "review_file": ...}`.
4. If **APPROVE**: mill-go sets `approved: true` in the plan, updates `status.md`, proceeds to Phase: Setup.
5. If **REQUEST_CHANGES**: mill-go reads the review report, invokes `mill-receiving-review`, applies fixes, writes a fixer report to `.mill/active/<slug>/reviews/<timestamp>-plan-fix-r<N>.md`, then re-spawns with the updated plan only.
6. **Non-progress detection.** If pushed-back findings are identical across rounds, mill-go blocks immediately.
7. Repeat until **APPROVE** or `max_plan_review_rounds` exhausted.
8. If unresolved BLOCKING issues remain: mill-go blocks with `Plan review dispute after <max> rounds`.

The loop implementation, non-progress detection, and v2 parallel fan-out logic live in `plugins/mill/skills/mill-go/SKILL.md` Phase: Plan Review.
