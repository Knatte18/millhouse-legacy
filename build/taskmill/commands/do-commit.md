---
description: "Implement the next planned task and commit"
model: sonnet
---

Implement the next planned task and commit. Combines `do` then `commit`.

## Steps

1. **Branch check:** run `git branch --show-current`. If on `main`/`master`:
   1. Derive a branch name from the task title slug (e.g. `feature/revise-git-workflow`).
   2. Prompt: *"You're on **main**. Create branch **`<name>`** and continue there? You can also provide a different name."*
   3. Wait for user confirmation or an alternative name.
   4. Run `git checkout -b <name>` to create and switch to the branch.
2. Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_get.py --include-planned doc/backlog.md` to find the next planned task.
   - Priority: first `[>]` with `plan:`, then first `[p]` with `plan:`, then first `[ ]` with `plan:`.
3. Read the plan file.
4. Read all files listed in `## Files` as initial context.
5. **Staleness check:** read the `started:` timestamp from the plan's YAML frontmatter and run `git log --since=<started-timestamp> -- <file1> <file2> ...` for the listed files. If changes are found, re-read affected files and revise plan steps before proceeding.
6. Implement each `- [ ]` step, marking as `- [x]` immediately after completion.
7. If a step fails: mark `- [!]` and block the task via `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_block.py`.
8. Run build + test after all steps. Use @taskmill:csharp-build skill.
9. If all steps complete: run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_complete.py --delete doc/backlog.md`, then update `doc/changelog.md`.
10. Commit and push: stage files individually, commit with title + bullet-point format, push. Set upstream if needed.
