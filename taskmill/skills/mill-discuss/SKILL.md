---
name: mill-discuss
description: "Discuss a backlog task without writing a plan"
argument-hint: "<task name>"
---

Discuss a backlog task. Does **not** write a plan.

## Steps

1. Run `python ${CLAUDE_SKILL_DIR}/../../scripts/task_claim.py doc/backlog.md <task-name>` to find and claim the task.
   - If a task name argument was provided, pass it to the script.
   - If no argument, the script selects the first `[>]`, then first `[ ]`.
   - `[N]` tasks (already claimed by another thread) are skipped.
2. If the claimed task has a `plan:` sub-bullet, read and summarize the existing plan, then continue discussion from there.
3. Read relevant codebase sections.
4. Ask clarifying questions about approach, constraints, and design.
5. Discussion continues until the user calls `finalize`.

## Rules

- Do not enter plan mode or write plan files. This command is discussion only.
- Do not edit any files other than `doc/backlog.md` (for claiming the task). No code edits, no file creation.
- Use @taskmill:mill-formats skill for backlog format rules.
