---
description: "Finalize the current discussion and implement that task (no commit)"
model: opus
---

Finalize the current discussion and immediately implement the resulting task. Does **not** commit.

## Steps

1. Take task name from argument or infer from conversation.
2. Create `.llm/plans/YYYY-MM-DD-HHMMSS-<slug>.md` (using current UTC date and time) with:
   - **YAML frontmatter:** `started:` (copied from the task's `started:` sub-bullet in `doc/backlog.md`) and `finished:` (current UTC timestamp, matches filename timestamp)
   - **Context:** summary of discussion and key decisions
   - **Files:** flat list of file paths the plan expects to modify
   - **Steps:** concrete, actionable `- [ ]` items
3. Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_plan.py doc/backlog.md "<task-name>" <plan-path>` to change state to `[p]` and add/replace the `plan:` sub-bullet.
4. Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_get.py --include-planned doc/backlog.md` to confirm the task is selected.
5. Read all files listed in `## Files` as initial context.
6. **Staleness check:** read the `started:` timestamp from the plan's YAML frontmatter and run `git log --since=<started-timestamp> -- <file1> <file2> ...`. If changes are found, re-read affected files and revise plan steps before proceeding.
7. Implement each `- [ ]` step, marking as `- [x]` immediately after completion.
8. If a step fails: mark `- [!]` and block via `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_block.py`.
9. Run build + test after all steps. Use @taskmill:csharp-build skill.
10. If all steps complete: run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_complete.py --delete doc/backlog.md`, then update `doc/changelog.md`.
11. Does **not** commit — user calls `commit` when ready.

## Rules

- Steps must use concrete actions, never `/taskmill.*` commands or `@taskmill:` skill references.
- Do not edit any files other than `.llm/plans/` during finalize. All backlog mutations go through scripts.
- Use @taskmill:formats skill for plan and backlog format rules.
