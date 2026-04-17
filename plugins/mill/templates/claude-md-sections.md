<!--
Template: CLAUDE.md Startup + Tasks sections.
Used by: plugins/mill/skills/mill-setup/SKILL.md (Step 7: Update CLAUDE.md).
Tokens: none (content is generic).
-->
## Startup
On first message in a conversation, invoke `mill:conversation` and `mill:workflow` before responding.

## Tasks

- Task list: `tasks.md` lives on an orphan branch `tasks` in this repo. Never merges to main. Git-synced across machines (pushed after every write).
- Local checkout: the `tasks` branch is checked out as a persistent git worktree at `tasks.worktree-path` in `_millhouse/config.yaml` (typically `<parent-of-repo>/<reponame>.worktrees/tasks`). Open a dedicated VS Code window on that worktree to edit tasks directly.
- Read/write access from any skill: always via `millpy.tasks.tasks_md.resolve_path(cfg)` and `tasks_md.write_commit_push(cfg, content, commit_msg)`. Never run `git` against `tasks.md` in the current worktree.
- Lifecycle markers: `[s]` (ready) → `[active]` (claimed) → `[completed]` (mill-go finished) → `[done]` (mill-merge landed). `[abandoned]` overwrites any of the above when mill-abandon runs.
- Phase tracking (per-task internal state): `_millhouse/task/status.md` — `phase:` field is the authoritative source. `## Timeline` section records chronological phase history.
- `_millhouse/` is gitignored (scoped to each worktree). On child-worktree spawn, it is copied (excluding `task/`, `scratch/`, and `children/`) from parent to new worktree.
- Run `mill-setup` to initialize after a fresh clone (safe to re-run; creates the tasks branch + worktree if missing).
- Format reference: `plugins/mill/doc/formats/tasksmd.md`.
