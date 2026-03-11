---
description: "Implement the next planned task"
model: opus
---

Implement the next planned task. Does **not** commit.

- Finds next planned task using `--include-planned`: first `[>]` with `plan:`, then first `[p]` with `plan:`, then first `[ ]` with `plan:`.
- Reads the plan file.
- Reads all files listed in `## Files` as initial context.
- **Staleness check:** reads the `started:` timestamp from the plan's YAML frontmatter and runs `git log --since=<started-timestamp> -- <file1> <file2> ...` for the listed files. If changes are found, re-reads affected files and revises plan steps before proceeding.
- Implements each `- [ ]` step. After completing each step, runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_complete.py <plan-file>` to mark it `[x]`.
- If a step fails: runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_block.py <plan-file> "<reason>"` to mark it `[!]`, then blocks the backlog task via `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_block.py doc/backlog.md "<reason>"`.
- Runs build + test after all steps (detect project language and use the matching `{lang}-build` skill — see `@taskmill:workflow` Language Detection).
- If all steps complete: deletes task from `doc/backlog.md` (via `--delete`), updates `doc/changelog.md`.
- Does **not** commit — user calls `commit` when ready.
