---
description: "Write a plan from the current discussion"
argument-hint: "[--park] [task name]"
---

Write a plan from the current discussion.

- Takes task name from argument or infers from conversation.
- Creates `.llm/plans/YYYY-MM-DD-HHMMSS-<slug>.md` (using current UTC date and time) with:
  - **YAML frontmatter:** `started:` (copied from the task's `started:` sub-bullet in `doc/backlog.md`) and `finished:` (current UTC timestamp, matches filename timestamp)
  - **Context:** summary of discussion and key decisions
  - **Files:** flat list of file paths the plan expects to modify (used for staleness detection and fast implementation start)
  - **Steps:** concrete, actionable `- [ ]` items (see step-writing rules below)
- **Park flag (`--park`):** When `--park` is in the argument, pass `--state ' '` to `task_plan.py` instead of the default `[p]`. This sets the task back to `[ ]` while preserving the `plan:` sub-bullet, signaling "partially discussed, parked for later." The `do` command requires `[p]`, so parked tasks won't execute.
- **Incomplete discussion guard:** If the discussion has not produced concrete, complete steps covering all aspects of the task, prompt the user: *"This discussion seems incomplete. Finalize as planned (`[p]`) or park for later (`--park`)?"* Wait for the user's choice before proceeding.
- Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_plan.py doc/backlog.md "<task-name>" <plan-path>` to change state to `[p]` and add/replace the `plan:` sub-bullet. With `--park`: run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_plan.py --state ' ' doc/backlog.md "<task-name>" <plan-path>` instead.
- Do not edit any files other than `.llm/plans/`. No code edits, no build changes. All backlog mutations go through scripts.

### Step-writing rules

- **One step per file** (or a small cluster of tightly coupled files). Never bundle "create X, then wire it into Y, then update Z" into a single step.
- **Explicit names.** Each step must include the target file path and the specific functions, classes, or fields being added or changed.
- **No slash commands or skill references.** Steps must describe concrete actions, never `/taskmill.*` commands or `@taskmill:` skill names — the executor treats these as requiring user invocation, stalling execution.
- **Test steps required for source code tasks.** When `## Files` contains source code files, the plan must include steps for writing new tests or updating existing tests that cover the changes. Omit test steps only when the task is purely doc or config changes.
