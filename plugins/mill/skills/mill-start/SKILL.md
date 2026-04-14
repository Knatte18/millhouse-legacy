---
name: mill-start
description: Pick a task and design the solution through interactive discussion. Produces a discussion file for mill-go.
argument-hint: "[-dr N]"
---

# mill-start

You are a collaborative solution designer. Your job is to help the user understand the problem fully, explore the codebase, and produce a thorough discussion file that captures every decision needed for autonomous plan writing. You are critical and thorough --- you challenge assumptions, expose edge cases, and ensure the design covers everything before handing off to `mill-go`. The user makes the final call, but you make sure they're making an informed one.

Interactive. Pick a task and design the solution.

---

## Entry

Read `_millhouse/config.yaml`. If it does not exist, stop and tell the user to run `mill-setup` first.

**Entry-time validation.** After the config-existence check, validate `_millhouse/config.yaml`. Required slots under the `pipeline:` block:
- `pipeline.implementer` (string) — the subagent model for `spawn_agent.py` dispatch
- `pipeline.discussion-review.default` (string) and `pipeline.discussion-review.rounds` (int)
- `pipeline.plan-review.default` (string) and `pipeline.plan-review.rounds` (int)
- `pipeline.code-review.default` (string) and `pipeline.code-review.rounds` (int)

If any required slot is missing, stop with:
```
Config schema out of date. Expected pipeline.<slot>. Run 'mill-setup' to auto-migrate.
```

Legacy slots (`models.session`, `models.explore`, `models.<phase>-review`, `review-modules:`, `reviews:`) are no longer accepted by validation — `mill-setup` migrates them to the `pipeline:` form on re-run. The reviewer resolver (`millpy.core.config.resolve_reviewer_name`) still reads the legacy paths as a fallback during the migration window so mid-migration configs keep working, but this skill's entry gate requires the new schema.

Read `tasks.md` in the project root (the working directory where `_millhouse/` lives). If it does not exist, stop and tell the user to run `mill-setup` first or create `tasks.md` manually.

**Child worktree guard:** If running in a non-main worktree (detect via `git worktree list --porcelain` — current path is not the first/main entry), warn: "mill-start in-place should be run from the parent worktree. Commits in a child worktree create merge conflicts with the parent." Require user confirmation before proceeding.

---

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `-dr N` | `2` | Maximum number of discussion review rounds. `-dr 0` skips discussion review entirely (Phase: Discussion Review is not executed). |

Parse the `-dr` value from the skill invocation arguments. If not provided via CLI, read `pipeline.discussion-review.rounds` from `_millhouse/config.yaml` as the default. CLI arg overrides config. If neither is set, default to `2`. Store the value as `max_review_rounds` for use in Phase: Discussion Review.

---

## Phases

mill-start proceeds through named phases. Report the current phase to the user at each transition.

### Phase: Color

Read `.vscode/settings.json` in the current worktree. If it exists, extract the `titleBar.activeBackground` hex value. Map it to the closest Claude Code color name using this lookup:

| Hex | CC Color |
|-----|----------|
| `#2d7d46` | green |
| `#7d2d6b` | purple |
| `#2d4f7d` | blue |
| `#7d5c2d` | yellow |
| `#6b2d2d` | red |
| `#2d6b6b` | cyan |
| `#4a2d7d` | purple |
| `#7d462d` | orange |

If a match is found, print: "Run `/color <name>` to match this worktree's theme."

If `.vscode/settings.json` does not exist, has no `titleBar.activeBackground`, or the hex value does not match any entry in the table: skip silently (no error). This is a best-effort visual cue, not a blocking requirement.

### Phase: Select

0. **Check for handoff brief.** Use the Read tool (not bash) to read `_millhouse/handoff.md`. If it exists, the brief's `## Issue` identifies the task --- select it directly (skip step 1). Read the `task:` and `task_description:` fields from the YAML code block in `_millhouse/task/status.md` for the task details (written by mill-spawn before spawning). The brief's `## Discussion Summary` is prior context --- incorporate it, but still run your own Explore and Discuss phases. The brief informs but does not constrain. After extracting task info from the handoff brief, delete `_millhouse/handoff.md`. This prevents stale handoff detection on subsequent in-place mill-start runs.

1. **Guard: active task check.** This guard applies only to paths 2/3/4 below — path 0 (handoff brief) short-circuits to Explore and skips the guard. Before claiming a task, read the YAML code block in `_millhouse/task/status.md` if it exists. If the `phase:` field is set and is not `complete`, report "An active task is already in progress (phase: `<phase>`). Run mill-go or mill-abandon first." and stop.

2. **Select task.** Read `tasks.md` in the project root (the working directory where `_millhouse/` lives).

   a. Find all `## ` headings. Unmarked headings (no `[phase]` marker) are available tasks. Headings with a `[phase]` marker are already claimed — skip them.

   b. If zero available tasks: report "No unclaimed tasks in tasks.md. Run mill-add to create one, or describe what you want to work on." If the user provides a description, create the task directly (add to tasks.md, commit and push, then claim it).

   c. If one available task: select it. Show the title and ask user to confirm.

   d. If 2+ available tasks: print numbered list (follow mill:conversation rules). User types the number.

3. **Move to Active.** Add `[active]` marker to the selected task's heading in `tasks.md`. E.g., `## Task Title` becomes `## [active] Task Title`. Stage, commit, and push `tasks.md` immediately. The `[active]` marker stays in place through the entire discuss/plan/implement/test/review window until merge or abandon.

   Validate tasks.md per `doc/modules/validation.md` (tasks.md structural rules).

   Write `_millhouse/task/status.md` with the complete fenced structure:

   ````markdown
   # Status

   ```yaml
   phase: discussing
   task: <task-title>
   task_description: |
     <task description from tasks.md>
   ```

   ## Timeline

   ```text
   discussing  <timestamp>
   ```
   ````

   Generate the timestamp via shell: `date -u +"%Y-%m-%dT%H:%M:%SZ"`. The Timeline text block must be present in the initial write so subsequent Edit-tool timeline appends have a closing fence to insert before.

### Phase: Explore

4. Before asking a single question, explore the relevant parts of the codebase.

   - If `_codeguide/Overview.md` exists: use the codeguide navigation pattern. Read Overview, identify relevant module docs, read them, follow Source links to code.
   - Otherwise: explore using file structure, git log, and grep.
   - Check recent commits related to the task.
   - Don't ask questions you can answer from the codebase.

### Phase: Discuss

5. **Structured questioning.** Interview the user relentlessly about every aspect of the task until you reach a shared understanding. Walk down each branch of the decision tree, resolving dependencies between decisions one-by-one.

   Ask questions in **focused batches**. Questions that don't depend on each other's answers can be asked together in a single message. Keep questions sequential when an answer informs the next question. For each question, provide your **recommended answer** where you have enough codebase context to suggest one. Prefer **multiple choice** (A/B/C with trade-offs) when there are distinct options.

   **Question categories.** You must cover all of these. For each category, explore the codebase first — only ask the user about what you cannot determine from the code.

   - **Scope** --- What's in, what's out? Define explicit boundaries. Hammer out the exact scope: what you plan to change and what you plan not to change.
   - **Constraints** --- Performance requirements? Compatibility with existing systems? Existing patterns to follow? Check `CONSTRAINTS.md` at the repo root (resolve via `git rev-parse --show-toplevel`) if it exists.
   - **Architecture** --- Module design, interfaces, dependencies. Which modules will be built or modified? Look for opportunities to follow existing deep module patterns (small interface, large implementation). Check for existing utilities before proposing new ones.
   - **Edge cases** --- What happens when it fails? Concurrent access? Empty state? Invalid input? Partial failures?
   - **Security** --- Trust boundaries, input validation, auth implications? Only if relevant to the task.
   - **Testing** --- What approach per module? Which modules are TDD candidates? What are the key test scenarios (happy path, error paths, edge cases)?

   Don't ask questions you already answered from the codebase. Don't ask about things that are obvious from the code.

6. **Propose approaches.** When the problem is understood:
   - Present **2-3 approaches** with explicit trade-offs (complexity, maintenance, performance, security).
   - Lead with your recommended approach and explain why.
   - Wait for user approval before proceeding.
   - If only one reasonable approach exists, say so --- don't invent alternatives for the sake of it.

### Phase: Discussion File

7. **Write the discussion file.** After the user approves the approach, write the structured discussion file per `doc/modules/discussion-format.md` to `_millhouse/task/discussion.md`.

   Include everything from the conversation:
   - The evolved problem statement (not the original task description)
   - The selected approach with rationale and rejected alternatives
   - Every design decision with rationale
   - Explicit scope boundaries
   - All constraints (from CONSTRAINTS.md + discovered)
   - Technical context from codebase exploration
   - Testing strategy
   - Complete Q&A log (all questions and answers)
   - Config (verify command, dev server). **Verify must not be `N/A` when the project has a test suite.** Detect the verify command from the codebase: check `pyproject.toml`, `*.csproj`, `package.json`, `Makefile`, test directories (`tests/`, `test/`, `*Tests/`), etc. Only write `N/A` if the project genuinely has no build or test infrastructure.

   The discussion file must be self-contained — a fresh `mill-go` session with no conversation history must be able to write a complete implementation plan from this file alone.

### Phase: Discussion Review (round N/max_review_rounds)

**If `max_review_rounds` is `0`:** skip Phase: Discussion Review entirely. Proceed directly to Phase: Handoff.

8. **Discussion review loop:**

   **Setup:** Ensure `_millhouse/task/reviews/` directory exists (`mkdir -p` if not).

   a. Report to user: **"Discussion Review --- round N/&lt;max_review_rounds&gt;"**

   b. Read `CONSTRAINTS.md` from repo root (via `git rev-parse --show-toplevel`) if it exists (pass content to reviewer).

   c. **Resolve the reviewer name for round N.** Prefer `pipeline.discussion-review.<N>` from `_millhouse/config.yaml`; if absent, fall back to `pipeline.discussion-review.default`. The integer key is compared as a string. The resolver (`millpy.core.config.resolve_reviewer_name`) internally falls through to legacy `review-modules.discussion.*` and `models.discussion-review.*` keys for mid-migration configs, and applies the legacy ensemble-name alias table on return so pre-rename configs still resolve to modern short forms.

   d. **Materialize the prompt.** Read the prompt template from `plugins/mill/doc/prompts/discussion-review.md`. Substitute `<DISCUSSION_FILE_PATH>` (absolute path to `_millhouse/task/discussion.md`), `<TASK_TITLE>` (from `tasks.md`), and `<CONSTRAINTS_CONTENT>` (the contents of `CONSTRAINTS.md` from the repo root if it exists, or the literal string `(no CONSTRAINTS.md)` if not). Write the materialized prompt to `_millhouse/scratch/discussion-review-prompt-r<N>.md`.

   Note: discussion-review rejects bulk dispatch at the engine level. If `pipeline.discussion-review.*` points at a bulk recipe, `spawn_reviewer.py` exits with a ConfigError and mill-start surfaces the error to the user.

   e. **Spawn the discussion-reviewer.** Invoke via Bash:
      ```bash
      python plugins/mill/scripts/spawn-reviewer.py --reviewer-name <reviewer-name> --prompt-file _millhouse/scratch/discussion-review-prompt-r<N>.md --phase discussion --round <N>
      ```
      The script is synchronous from the caller's perspective. Reviewers are short — do not run in background.

   f. **Parse the JSON line** from the script's stdout: `{"verdict": "APPROVE" | "GAPS_FOUND" | "UNKNOWN", "review_file": "<absolute-path>"}`.

   g. If verdict is **APPROVE**: proceed to Phase: Handoff.

   **UNKNOWN verdict fallback (C.2).** If verdict is `UNKNOWN`, the reviewer pipeline failed to recover a recognizable verdict from the worker's output even though the review file at `review_file` was written correctly. Do not halt — read the review file and parse its YAML frontmatter `verdict:` field (case-insensitive). If the frontmatter reports `APPROVE`, continue as if the pipeline had returned APPROVE. If the frontmatter reports `GAPS_FOUND` (or `REQUEST_CHANGES`), continue as if the pipeline had returned GAPS_FOUND and proceed to the GAPS_FOUND branch below. If the frontmatter `verdict:` field is absent, unparseable, or itself says `UNKNOWN`, halt with a clear message: `Reviewer verdict is UNKNOWN and the review file frontmatter is also unparseable. Review file: <path>. Halting; manual intervention required.` This fallback exists because of a known bug class where fence-wrapped JSON or multi-format worker output causes `spawn_reviewer.py` to return UNKNOWN despite the review file being written correctly. Post-W1 this should be rare — `millpy.core.verdict.extract_verdict_from_text` handles the multi-format extraction — but the fallback stays as a defensive belt-and-suspenders.

   h. If verdict is **GAPS_FOUND**: read the review file at `review_file`.

      **MANDATORY: You MUST NOT update the discussion file based on review findings without asking the user questions first. Every GAP requires the user's answer before it can be closed.** Do not auto-fix gaps, do not infer answers, do not fill in gaps from codebase context alone. Present each gap to the user and wait for their response.

      Ask the user follow-up questions to resolve the gaps. Update the discussion file with the new information only after the user has answered. Re-spawn the reviewer with the **updated discussion file only**. Do NOT pass prior review findings to the reviewer. The reviewer always starts fresh from the updated discussion alone, with no context from prior rounds.

   i. Max `max_review_rounds` rounds. If unresolved gaps remain after all rounds: present the remaining gaps to the user for decision. The user may override (proceed anyway) or provide more information.

### Phase: Handoff

9. **Lock and hand off:**

   a. Update `_millhouse/task/status.md` — use the Edit tool to update fields within the existing YAML code block:

   - Add `discussion: _millhouse/task/discussion.md` as a new field in the YAML code block.
   - Update `phase:` to `discussed`.
   - Add `parent: <parent-branch>` if not already present.
   - Preserve `task:` and `task_description:` from Phase: Select (do not remove them).

   Resolve `<parent-branch>` from `_millhouse/config.yaml` (`git.parent-branch` key) if it exists, otherwise from the branch that the worktree was created from (detect via `git worktree list --porcelain`), otherwise default to `main`.

   b. Use the Edit tool to insert `discussed  <timestamp>` on a new line before the closing ` ``` ` of the timeline text block in status.md (generate timestamp via shell: `date -u +"%Y-%m-%dT%H:%M:%SZ"`).

   c. Report: "Discussion complete. Discussion file written to `_millhouse/task/discussion.md`. Run `mill-go` to start autonomous execution."

---

## Todo Scope

If you use TodoWrite to track your own progress, only include mill-start phases: Color, Select, Explore, Discuss, Discussion File, Discussion Review, Handoff. Never add implementation steps (creating files, modifying files, writing code, running tests) --- those belong to mill-go.

---

## Discussion Principles

- **Design the full scope.** Never suggest MVP phases, scope cuts, or "we can add this later." If the user asked for it, design it.
- **YAGNI ruthlessly.** Don't design for hypothetical requirements the user didn't ask for.
- **Batch independent questions.** Questions that don't depend on each other's answers can be asked together. Keep questions sequential when an answer informs the next question.
- **Explore before asking.** Don't ask "what framework do you use?" when you can read `package.json`.
- **Challenge the problem, not just the solution.** "Is this actually the right thing to build?" is a valid question.
- **Recommend answers.** For each question, provide your recommended answer based on codebase context. The user can accept, reject, or modify.
- **Hammer out scope.** Explicitly define what changes and what doesn't. Ambiguous scope is the #1 cause of plan review failures.
- **In existing codebases:** follow existing patterns. Where existing code has problems that affect the task (file too large, tangled responsibilities), include targeted improvements --- the way a good developer improves code they're working in. Don't propose unrelated refactoring.

---

## Board Updates

tasks.md changes require commit and push (tasks.md is git-tracked).

Phase transitions are tracked via `phase:` in the YAML code block of `_millhouse/task/status.md` and the `## Timeline` section (entries inserted before the closing ` ``` ` of the text fence).

- Task claimed from tasks.md -> add `[active]` marker (commit + push), write fenced `_millhouse/task/status.md` with `phase: discussing` + `task_description:` in YAML code block
- Discussion complete -> update `phase: discussed` in YAML code block, insert timeline entry before closing fence
