---
description: "Finalize the current discussion, implement that task, and commit"
model: opus
---

Finalize the current discussion, implement the resulting task, and commit.

## Steps

1. **Branch check:** run `git branch --show-current`. If on `main`/`master` and `--onmain` is not in the argument: refuse. Suggest a branch name based on the task context (e.g. `feature/task-name`), prompt the user to create it and re-run. Do not create the branch.
2. Take task name from argument or infer from conversation.
3. Create `.llm/plans/YYYY-MM-DD-HHMMSS-<slug>.md` (using current UTC date and time) with YAML frontmatter, context, files, and steps.
4. Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_plan.py doc/backlog.md "<task-name>" <plan-path>` to change state to `[p]` and add/replace the `plan:` sub-bullet.
5. Read all files listed in `## Files` as initial context.
6. **Staleness check:** read the `started:` timestamp from the plan's YAML frontmatter and run `git log --since=<started-timestamp> -- <file1> <file2> ...`. If changes are found, re-read affected files and revise plan steps.
7. Implement each `- [ ]` step, marking as `- [x]` immediately after completion.
8. If a step fails: mark `- [!]` and block via `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_block.py`.
9. Run build + test after all steps. Use @taskmill:csharp-build skill.
10. If all steps complete: run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_complete.py --delete doc/backlog.md`, then update `doc/changelog.md`.
11. Commit and push: stage files individually, commit with title + bullet-point format, push. Set upstream if needed.

## Rules

- Steps must use concrete actions, never `/taskmill.*` commands or `@taskmill:` skill references.
- Do not edit any files other than `.llm/plans/` during finalize. All backlog mutations go through scripts.
- Use @taskmill:formats skill for plan and backlog format rules.
