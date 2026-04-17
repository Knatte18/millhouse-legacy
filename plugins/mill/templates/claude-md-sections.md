<!--
Template: CLAUDE.md Startup + Tasks sections.
Used by: plugins/mill/skills/mill-setup/SKILL.md (Step 7: Update CLAUDE.md).
Tokens: none (content is generic).
-->
## Startup
On first message in a conversation, invoke `mill:conversation` and `mill:workflow` before responding.

## Tasks

- Task list: `tasks.md` in project root — git-tracked, `## ` headings for tasks, optional `[phase]` markers.
- Phase tracking: `_millhouse/task/status.md` — `phase:` field is the authoritative source. `## Timeline` section records chronological phase history.
- `_millhouse/` is gitignored. On spawn, it is copied (excluding `task/`, `scratch/`, and `children/`) from parent to new worktree.
- Run `mill-setup` to initialize after a fresh clone (safe to re-run; skips existing files).
- Format reference: `plugins/mill/doc/formats/tasksmd.md` (tasks.md format).
