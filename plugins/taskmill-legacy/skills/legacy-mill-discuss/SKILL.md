---
name: legacy-mill-discuss
description: "Discuss a backlog task without writing a plan"
argument-hint: "<task name>"
---

Discuss a backlog task. Does **not** write a plan.

## Steps

1. Run `python ${CLAUDE_SKILL_DIR}/../../scripts/task_claim.py _millhouse/taskmill/backlog.md <task-name>` to find and claim the task.
   - If a task name argument was provided, pass it to the script.
   - If no argument, the script selects the first `[>]`, then first `[ ]`.
   - `[N]` tasks (already claimed by another thread) are skipped.
2. If `_codeguide/Overview.md` exists anywhere in the repo, read it. Use its module table and routing hints to navigate to the relevant module docs and source files in steps 4–5 — do not search blindly.
3. If the claimed task has a `plan:` sub-bullet, read and summarize the existing plan, then continue discussion from there.
4. Read relevant codebase sections (routed via codeguide if available, otherwise search).
5. Ask clarifying questions about approach, constraints, and design.
6. Discussion continues until the user calls `finalize`.

## Rules

- Do not enter plan mode or write plan files. This command is discussion only.
- Do not edit any files other than `_millhouse/taskmill/backlog.md` (for claiming the task). No code edits, no file creation.
- Use @taskmill-legacy:legacy-mill-formats skill for backlog format rules.
