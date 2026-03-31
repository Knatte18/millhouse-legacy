---
name: mill-review
description: "Review a plan by spawning a fresh agent with no conversation context"
argument-hint: "<task name>"
---

Review a backlog task's plan using a fresh agent that has no context from the current conversation. The agent reads the plan and codebase independently and produces a bullet-point report.

## Steps

1. Read `_taskmill/backlog.md`. Find the task matching the argument (or if no argument, the first `[p]` task). Extract the task description, any sub-bullets (especially `plan:`), and all context lines.
2. Assert that the task has a `plan:` sub-bullet. If not, exit with: "Task has no plan. Run /mill-finalize first."
3. Run `python ${CLAUDE_SKILL_DIR}/../../scripts/utcnow.py` to get a timestamp. **Do not guess or fabricate a timestamp.**
4. Derive a slug from the task name (lowercase, hyphens, max 40 chars).
5. Spawn a review agent using the Agent tool with `subagent_type: general-purpose` and `model: sonnet`. Pass the following prompt verbatim, substituting `<TASK_NAME>`, `<TASK_DESCRIPTION>`, `<TASK_SUBBULLETS>`, and `<PLAN_PATH>`:

   ---
   You are a plan reviewer. You have no context from any prior discussion. Your job is to evaluate whether the plan is ready for implementation.

   **FIRST ACTION — mandatory before anything else:**
   Read `_codeguide/Overview.md` if it exists. Use its module table and routing hints to navigate to relevant source files. If it does not exist, proceed without it.

   **Then do the following in order:**

   1. Read the plan file: `<PLAN_PATH>`
   2. Read the task entry from `_taskmill/backlog.md` — task name: `<TASK_NAME>`, description: `<TASK_DESCRIPTION>`, sub-bullets: `<TASK_SUBBULLETS>`
   3. Read at least 2 existing SKILL.md files in `plugins/taskmill/skills/` to understand the expected convention.
   4. Read any source files referenced in the plan's `## Files` section.

   **Produce a bullet-point report covering all of the following. Include every point — do not skip any even if there are no issues:**

   - **Concreteness:** Are the steps specific enough to implement without ambiguity? Are there compound steps that should be split?
   - **File/module references:** Do all file paths, function names, and script references in the steps match what actually exists in the codebase?
   - **Missing steps:** Are there steps required to complete the task that are not in the plan? (e.g. directory creation, install/deploy, updating related config)
   - **Scope:** Is the scope of the task appropriate — not too large, not underspecified?
   - **Alignment:** Does the plan match the task description and sub-bullet context?
   - **Convention compliance:** Does the SKILL.md structure follow the pattern of existing skills (frontmatter, sections, script paths using `${CLAUDE_SKILL_DIR}`)?
   - **Bottom line:** One or two sentences summarising readiness and any blockers.

   Return only the report. No preamble, no closing remarks.
   ---

6. Create the directory `.llm/reviews/` if it does not exist. Write the agent's report to `.llm/reviews/<timestamp>-<slug>.md`.
7. Run `python ${CLAUDE_SKILL_DIR}/../../scripts/task_subbullet.py _taskmill/backlog.md "<task-name>" "review: .llm/reviews/<timestamp>-<slug>.md"` to link the report on the backlog task.
8. Output the full report to the user.

## Rules

- Do not edit any code files. This skill only writes to `.llm/reviews/` and updates the backlog sub-bullet via script.
- Do not modify the plan file.
- The agent must be spawned with `model: sonnet` — do not use the default model.
