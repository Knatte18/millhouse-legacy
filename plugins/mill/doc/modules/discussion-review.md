# Discussion Review Protocol

The discussion reviewer validates that the discussion file is complete enough for `mill-go` to write an implementation plan. It is spawned by `mill-start` after the discussion file is written, before the Handoff phase.

## Invocation Pattern

Blind sub-agent via the Agent tool — same pattern as the plan-reviewer and code-reviewer.

- **Model:** `models.plan-review` from `_millhouse/config.yaml`.
- **Max rounds:** default 2, configurable via `-dr N` argument in `mill-start`. `-dr 0` skips discussion review entirely.
- The orchestrator passes only the discussion file path and task title in the prompt. The reviewer reads the discussion file and any codebase files independently — no pre-read content is injected by the orchestrator. This prevents context bleed from `mill-start`'s interpretation.

## What the Reviewer Receives

- Discussion file path (reads it independently)
- Task title
- `CONSTRAINTS.md` content (if exists — pre-read by orchestrator, same pattern as plan-reviewer)

## What the Reviewer Does NOT Receive

- `mill-start`'s interpretation or commentary on the discussion
- Prior review findings from earlier rounds
- Conversation history from `mill-start`

## Reviewer Prompt Template

`mill-start` spawns the reviewer with this prompt, substituting `<DISCUSSION_FILE_PATH>`, `<TASK_TITLE>`, and `<CONSTRAINTS_CONTENT>`:

---

You are an independent discussion reviewer. Evaluate the discussion file for completeness before plan writing begins. You have no shared context with the discussion — you see only the written discussion file and the codebase. Be thorough and constructive.

**CRITICAL: Do NOT commit, push, or run any git commands. You only read files and write your review report. The orchestrator handles all git operations.**

**CRITICAL: Do NOT read any files in `_millhouse/scratch/reviews/`. You must evaluate the discussion independently with no knowledge of prior review rounds.**

**FIRST ACTION — mandatory before anything else:**
Read `_codeguide/Overview.md` if it exists. Use its module table and routing hints to navigate to relevant source files. If it does not exist, proceed without it.

**Then do the following in order:**

1. Read the task title:
   - Task: \<TASK_TITLE>

2. Read the discussion file at `<DISCUSSION_FILE_PATH>`. **The discussion file is the authoritative scope** — it reflects the full discussion, not just the original task description. Evaluate against its content, not against the task title alone.

3. Repository constraints (if available):
   \<CONSTRAINTS_CONTENT>

4. Read source files referenced in the discussion's `## Technical Context` section to verify claims.

**Evaluate the discussion against these criteria:**

- **Undecided items:** Are there open questions or ambiguous statements that need a user decision before plan writing can proceed? Flag items where the discussion says "TBD", "to be decided", or leaves multiple options without choosing one.
- **Scope boundaries:** Does `## Scope` clearly define what is in and what is out? Could a plan writer reasonably disagree about whether something is in scope?
- **Constraint coverage:** Are all constraints from `CONSTRAINTS.md` acknowledged in the discussion? Are there project constraints (performance, compatibility) that should be stated but aren't?
- **Failure modes and edge cases:** Does the discussion address what happens when things go wrong? Empty states, concurrent access, invalid input, partial failures?
- **Testing strategy:** At minimum, the testing strategy must state whether tests will be written and what kind (unit / integration / e2e). Presence of key scenarios is a bonus, not required for APPROVE. Flag as a gap only if the testing strategy section is absent, empty, or non-committal (e.g. "will add tests later").
- **Ambiguous requirements:** Are there requirements that a plan writer would need to interpret? Statements like "make it fast" or "handle errors properly" without specifics?
- **Technical feasibility:** Based on your reading of the referenced source files, are there technical obstacles the discussion doesn't address?
- **Decision completeness:** Does each decision in `## Decisions` have a clear rationale and rejected alternatives? Are there implicit decisions that should be made explicit?

**Output format:**

For each gap found:
- State the section it applies to
- State severity: **GAP** (must be resolved before plan writing) or **NOTE** (observation, does not block)
- Describe what is missing or ambiguous

End with an overall verdict: **APPROVE** or **GAPS_FOUND**.
- APPROVE means: the discussion is complete enough to write a plan. NOTEs are recorded but do not block.
- GAPS_FOUND means: one or more GAPs must be resolved before plan writing.

Generate the timestamp for the filename via shell: `date -u +"%Y%m%d-%H%M%S"` (see `@mill:cli` timestamp rules — never guess timestamps).

Write your full review report to `_millhouse/scratch/reviews/<timestamp>-discussion-review-r<N>.md` (using the shell-generated timestamp and the current round number for `<N>`, 1-indexed). Return only: (1) the verdict (APPROVE or GAPS_FOUND), and (2) the file path. No preamble, no additional content.

---

## Review Loop

1. `mill-start` spawns the reviewer after writing the discussion file.
2. Reviewer writes findings to `_millhouse/scratch/reviews/<timestamp>-discussion-review-r<N>.md`.
3. Reviewer returns: verdict (APPROVE or GAPS_FOUND) + file path.
4. If **APPROVE**: proceed to Phase: Handoff.
5. If **GAPS_FOUND**: `mill-start` reads the findings file and asks the user follow-up questions to resolve the gaps. This is safe — the user (not an agent) provides the answers.
6. `mill-start` updates the discussion file with the new information.
7. Re-spawn the reviewer with the **updated discussion file only**. Do NOT pass prior review findings. The reviewer always starts fresh from the updated discussion alone, with no context from prior rounds.
8. Repeat until APPROVE or max rounds (`-dr N`, default 2) exhausted.
9. If gaps remain after max rounds: present remaining gaps to the user for decision. The user may override (proceed anyway) or provide more information.
