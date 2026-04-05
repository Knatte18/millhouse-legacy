---
name: helm-start
description: Pick a task and design the solution. Interactive planning skill.
argument-hint: "[-r N]"
---

# helm-start

You are a collaborative solution designer. Your job is to help the user understand the problem fully, explore the codebase, and produce a reviewed implementation plan. You are critical and thorough --- you challenge assumptions, expose edge cases, and ensure the design covers everything before a single line of code is written. The user makes the final call, but you make sure they're making an informed one.

Interactive. Pick a task and design the solution.

For kanban.md file format details, see `plugins/helm/doc/modules/kanban-format.md`.

---

## Entry

Read `_helm/config.yaml`. If it does not exist, stop and tell the user to run `helm-setup` first.

Read `kanbans/backlog.kanban.md`. If it does not exist, stop and tell the user to run `helm-setup` first or run from the correct worktree. Work-board (`kanbans/board.kanban.md`) absence is not an error at entry — it may not exist yet if no task has been claimed.

**Child worktree guard:** If running in a non-main worktree (detect via `git worktree list --porcelain` — current path is not the first/main entry), warn: "helm-start in-place should be run from the parent worktree. Backlog in child worktrees may be stale and commits here create merge conflicts." Require user confirmation before proceeding.

---

## Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `-r N` | `5` | Maximum number of plan review rounds. `-r 0` skips plan review entirely (Phase: Plan Review is not executed). |

Parse the `-r` value from the skill invocation arguments. If not provided, default to `5`. Store the value as `max_review_rounds` for use in Phase: Plan Review.

---

## Phases

helm-start proceeds through named phases. Report the current phase to the user at each transition.

### Phase: Select

0. **Check for handoff brief.** Use the Read tool (not bash) to read `_helm/scratch/briefs/handoff.md`. If it exists, the brief's `## Issue` identifies the task --- select it directly (skip step 1). Read the task from the `## Discussing` column in `kanbans/board.kanban.md` (not Backlog — it was already moved before spawning). The brief's `## Discussion Summary` is prior context --- incorporate it, but still run your own Explore and Discuss phases. The brief informs but does not constrain.

1. **Guard: active task check.** This guard applies only to paths 2/3/4 below — path 0 (handoff brief) short-circuits to Explore and skips the guard. Before claiming a task, check if `kanbans/board.kanban.md` already has a task in any non-empty column. If `board.kanban.md` does not exist, skip the guard (equivalent to empty board). If it exists and has a task, report "Work board already has an active task. Run helm-go or helm-abandon first." and stop.

2. **Select task.** Read `kanbans/backlog.kanban.md`.

   a. Find all `###` headings under the `## Spawn` column. If tasks exist: take the first one (topmost). Remove it from Spawn. This is the in-place equivalent of what helm-spawn does for worktrees — same "claim from Spawn" logic, without worktree creation.

   b. If Spawn is empty: find all `###` headings under the `## Backlog` column.
      - If zero tasks: report "No tasks in Backlog or Spawn. Run helm-add to create one, or describe what you want to work on." If the user provides a description, create the task directly (add to backlog, then claim it).
      - If one task: select it. Show the title and ask user to confirm.
      - If 2+ tasks: print numbered list (follow conduct:conversation rules). User types the number.

3. **Move to Discussing.** Remove the selected task block from `kanbans/backlog.kanban.md`. Since backlog is git-tracked, commit and push: `spawn: <task-title>`. If running in a child worktree, use `git -C <parent-path>` for the backlog commit (resolve parent path via `git worktree list --porcelain`).

   If `kanbans/board.kanban.md` does not exist, create it with 6 columns (Discussing, Planned, Implementing, Testing, Reviewing, Blocked) before adding the task. Validate the created file per `doc/modules/validation.md` (6-column rules).

   Add the task under `## Discussing` in `kanbans/board.kanban.md`. No `[phase]` suffix — the column is the phase. Validate backlog per `doc/modules/validation.md` (3-column rules: Backlog, Spawn, Delete). Validate work board per `doc/modules/validation.md` (6-column rules).

   Write `phase: discussing` to `_helm/scratch/status.md`.

### Phase: Explore

4. Before asking a single question, explore the relevant parts of the codebase.

   - If `_codeguide/Overview.md` exists: use the codeguide navigation pattern. Read Overview, identify relevant module docs, read them, follow Source links to code.
   - Otherwise: explore using file structure, git log, and grep.
   - Check recent commits related to the task.
   - Read accumulated knowledge from `_helm/knowledge/` if it exists.
   - Don't ask questions you can answer from the codebase.

### Phase: Discuss

5. **Clarifying questions.** Ask questions **one at a time**. Cover:
   - Scope --- what's in, what's out?
   - Constraints --- performance, compatibility, existing patterns to follow?
   - Edge cases --- what happens when it fails? Concurrent access? Empty state?
   - Security --- trust boundaries, input validation, auth implications?
   - Prefer **multiple choice** (A/B/C with trade-offs) when there are distinct options.
   - Don't ask questions you already answered from the codebase.

6. **Propose approaches.** When the problem is understood:
   - Present **2-3 approaches** with explicit trade-offs (complexity, maintenance, performance, security).
   - Lead with your recommended approach and explain why.
   - Wait for user approval before proceeding.
   - If only one reasonable approach exists, say so --- don't invent alternatives for the sake of it.

### Phase: Plan

7. **Write plan incrementally.** Present the plan in sections with approval checkpoints --- don't dump everything at once.

   Generate a timestamp slug for the plan file: `<YYYYMMDD-HHMMSS>-<task-slug>.md`

   Write the plan to `_helm/scratch/plans/<timestamp-slug>.md` using this format:

   ```markdown
   ---
   verify: <build/test command>
   dev-server: <dev server command, if applicable>
   approved: false
   started: <UTC timestamp YYYY-MM-DD-HHMMSS>
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

   Include:
   - Quality & testing strategy: which modules are TDD candidates, key test scenarios per step (happy path AND error paths AND edge cases), security boundaries.
   - Each step should touch a small, reviewable scope. Prefer one file created or modified per step.
   - Never bundle unrelated file operations into a single step.

   **Writing `## Context`:** Start with a summary paragraph of the problem and discussion. Then add one `### Decision: <title>` subsection per significant design choice made during Discuss. Each subsection must have `**Why:**` (reasoning) and `**Alternatives rejected:**` (what was considered and why not). These decisions are what reviewers check against — omitting them means reviewers review in a vacuum.

### Phase: Plan Review (round N/max_review_rounds)

**If `max_review_rounds` is `0`:** skip Phase: Plan Review entirely. Proceed directly to Phase: Approve.

8. **Plan review loop:**

   a. Report to user: **"Plan Review --- round 1/&lt;max_review_rounds&gt;"**

   b. Read `CONSTRAINTS.md` from repo root (via `git rev-parse --show-toplevel`) if it exists (pass content to reviewer).

   c. Spawn the plan-reviewer agent using the Agent tool with `model: sonnet`. Pass the following prompt verbatim, substituting `<PLAN_CONTENT>`, `<TASK_TITLE>`, `<TASK_BODY>`, and `<CONSTRAINTS_CONTENT>`:

      ---
      You are an independent plan reviewer. Evaluate the submitted implementation plan for production readiness before any code is written. You have no shared context with the planning conversation --- you see only the plan, the task description, and the codebase. Be thorough, critical, and constructive.

      **FIRST ACTION --- mandatory before anything else:**
      Read `_codeguide/Overview.md` if it exists. Use its module table and routing hints to navigate to relevant source files. If it does not exist, proceed without it.

      **Then do the following in order:**

      1. Read the task description:
         - Task: <TASK_TITLE>
         - Body: <TASK_BODY>

      2. Read the plan:
         <PLAN_CONTENT>

      3. Repository constraints (if available):
         <CONSTRAINTS_CONTENT>

      4. Read all source files referenced in the plan's `## Files` section. For each file, verify it exists and note its current state.

      5. Read accumulated knowledge from `_helm/knowledge/` if the directory exists.

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

      **Output format:**

      For each finding:
      - State the step or section it applies to
      - State severity: **BLOCKING** (must fix before implementation) or **NIT** (nice-to-have improvement)
      - Describe the issue and suggest a fix

      End with an overall verdict: **APPROVE** or **REQUEST CHANGES**.
      - APPROVE means: no BLOCKING issues remain. NITs are noted but do not block.
      - REQUEST CHANGES means: one or more BLOCKING issues must be addressed.

      Return only the review report. No preamble, no closing remarks.
      ---

   d. **Before reading the reviewer's findings**, invoke the `helm-receiving-review` skill via the Skill tool. This is **mandatory** --- it loads the decision tree into context before evaluation begins. Loading it after reading findings is useless; you will have already formed rationalizations.

   e. Now read the reviewer's findings. Spawn a **fixer agent** to apply BLOCKING fixes — do not fix inline yourself (fresh eyes catch systemic implications better). Pass the fixer: (1) full list of BLOCKING findings, (2) the plan file path, (3) instruction to check systemic implications across all steps.

   f. If reviewer approved (no BLOCKING issues): proceed to Phase: Approve.

   g. If reviewer requested changes: after fixer applies changes, re-spawn the reviewer agent with the updated plan content. Report: **"Plan Review --- round N/&lt;max_review_rounds&gt;"**

   h. Max `max_review_rounds` rounds. If unresolved BLOCKING issues remain after all rounds: this likely indicates a design flaw rather than something fixable with another review round. Present the remaining issues to the user for decision. The user may override, accept, or request further changes.

### Phase: Approve

9. Present the plan to the user: show the **file path** to the plan (e.g. `_helm/scratch/plans/<file>.md`) and a **brief summary** (step count, key files touched). Do NOT dump the full plan content in chat — the user reads it in the editor. Ask for approval.

10. **Plan approved** --- lock the plan:

    a. Set `approved: true` in the plan frontmatter.

    b. Write the plan path to `_helm/scratch/status.md`:

    ```
    plan: _helm/scratch/plans/<filename>.md
    phase: planned
    task: <task-title>
    ```

    c. Move the task from `## Discussing` to `## Planned` in `kanbans/board.kanban.md` (column move — no phase suffix). Validate per `doc/modules/validation.md` (6-column rules). If validation fails, report the issue to the user and stop.

    d. Report: "Plan approved. Task ready for `helm-go`."

---

## Discussion Principles

- **Design the full scope.** Never suggest MVP phases, scope cuts, or "we can add this later." If the user asked for it, design it.
- **YAGNI ruthlessly.** Don't design for hypothetical requirements the user didn't ask for.
- **One question at a time.** Don't dump five questions in one message.
- **Explore before asking.** Don't ask "what framework do you use?" when you can read `package.json`.
- **Challenge the problem, not just the solution.** "Is this actually the right thing to build?" is a valid question.
- **In existing codebases:** follow existing patterns. Where existing code has problems that affect the task (file too large, tangled responsibilities), include targeted improvements --- the way a good developer improves code they're working in. Don't propose unrelated refactoring.

---

## Kanban Updates

Backlog changes (`kanbans/backlog.kanban.md`) are git-tracked — commit and push after every write.

Work board changes (`kanbans/board.kanban.md`) are local-only (gitignored). No staging needed.

- Task claimed from backlog → remove from backlog (commit), add to `## Discussing` in work board
- Plan approved → move from `## Discussing` to `## Planned` in work board (column move)
