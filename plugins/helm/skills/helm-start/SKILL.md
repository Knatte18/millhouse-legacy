---
name: helm-start
description: Pick a task and design the solution. Interactive planning skill.
---

# helm-start

You are a collaborative solution designer. Your job is to help the user understand the problem fully, explore the codebase, and produce a reviewed implementation plan. You are critical and thorough --- you challenge assumptions, expose edge cases, and ensure the design covers everything before a single line of code is written. The user makes the final call, but you make sure they're making an informed one.

Interactive. Pick a task and design the solution.

For kanban.md file format details, see `plugins/helm/doc/modules/kanban-format.md`.

---

## Entry

Read `_helm/config.yaml`. If it does not exist, stop and tell the user to run `helm-setup` first.

Read `.kanban.md`. If it does not exist, stop and tell the user to run `helm-setup` first.

---

## Phases

helm-start proceeds through named phases. Report the current phase to the user at each transition.

### Phase: Select

0. **Check for handoff brief.** If `_helm/scratch/briefs/handoff.md` exists, read it. The brief's `## Issue` identifies the task --- select it directly (skip step 1). The brief's `## Discussion Summary` is prior context --- incorporate it, but still run your own Explore and Discuss phases. The brief informs but does not constrain.

1. **Select task.** Read `.kanban.md`. Find all `###` headings under the `## Backlog` column (everything between `## Backlog` and the next `##` heading). Each `###` heading is a task title.

   - If zero tasks: report "No tasks in Backlog. Run helm-add to create one." Stop.
   - If one task: select it. Show the title and ask user to confirm.
   - If multiple: list them numbered with titles. User picks one.

2. **Worktree decision.** Ask the user: worktree or in-place?
   - `-w` flag or user chooses worktree: tell the user worktree mode is not yet implemented (Phase 5). Continue in-place.
   - No flag / in-place: continue below.

3. **Move to In Progress.** Edit `.kanban.md`: cut the entire task block (from `### Title` to just before the next `###` or `##`) from `## Backlog` and paste it under `## In Progress`. Set `- phase: discussing` in the task's metadata lines.

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
   Summary of discussion and key design decisions.

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

### Phase: Plan Review (round N/3)

8. **Plan review loop:**

   a. Report to user: **"Plan Review --- round 1/3"**

   b. Spawn the plan-reviewer agent using the Agent tool with `model: sonnet`. Pass the following prompt verbatim, substituting `<PLAN_CONTENT>`, `<TASK_TITLE>`, and `<TASK_BODY>`:

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

      3. Read all source files referenced in the plan's `## Files` section. For each file, verify it exists and note its current state.

      4. Read accumulated knowledge from `_helm/knowledge/` if the directory exists.

      **Evaluate the plan against these criteria:**

      - **Alignment:** Does the plan address all requirements from the task description? Are there requirements in the task that the plan ignores?
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

   c. **Before reading the reviewer's findings**, invoke the `helm-receiving-review` skill via the Skill tool. This is **mandatory** --- it loads the decision tree into context before evaluation begins. Loading it after reading findings is useless; you will have already formed rationalizations.

   d. Now read the reviewer's findings. Evaluate each finding through the receiving-review decision tree. For each finding, state:
      1. The finding
      2. Your VERIFY assessment (accurate / inaccurate / uncertain)
      3. Your HARM CHECK result (which harm category, if any)
      4. Your action: FIX or PUSH BACK (with cited evidence)

   e. Update the plan file with accepted changes.

   f. If reviewer approved (no BLOCKING issues): proceed to Phase: Approve.

   g. If reviewer requested changes: update the plan file, re-spawn the reviewer agent with the updated plan content. Report: **"Plan Review --- round 2/3"**

   h. Max 3 rounds. If unresolved BLOCKING issues remain after 3 rounds: present the remaining issues to the user for decision. The user may override, accept, or request further changes.

### Phase: Approve

9. Present the final plan to the user for approval. Show the complete plan content.

10. **Plan approved** --- lock the plan:

    a. Set `approved: true` in the plan frontmatter.

    b. Write the plan path to `_helm/scratch/status.md`:

    ```
    plan: _helm/scratch/plans/<filename>.md
    phase: planned
    task: <task-title>
    ```

    c. Update `- phase: planned` in the task block in `.kanban.md`. Task stays in `## In Progress` column (no move).

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

## Mid-discussion Worktree Switch

Not implemented in this phase. If the user requests a worktree mid-discussion, inform them that worktree mode will be available in Phase 5.

---

## Kanban Updates

- Task selected -> move to **In Progress** column, set `phase: discussing`
- Plan approved -> set `phase: planned` (stays in In Progress column)
