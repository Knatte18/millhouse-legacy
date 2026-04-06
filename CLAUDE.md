# CLAUDE.md
Instructions for Claude Code when working in this repository.

## Background
- This repo is based on a repo by Craig Motlin. When referring to "what Motlin does", I am referring to his code and repo. The repo can be found here: "C:\Code\motlin-claude-code-plugins".
- Willie Tran's Autoboard is a reference system for autonomous agent orchestration. When referring to "what Tran does", I am referring to his code and repo. The repo can be found here: "C:\Code\autoboard".

## Repository structure

Millhouse is a multi-plugin marketplace for Claude Code. The core plugin is `mill`, with optional language-specific plugins.

### Plugins

| Directory | Plugin | Description |
|-----------|--------|-------------|
| `plugins/mill/` | mill | Task orchestration, code quality, git workflow, and documentation |
| `plugins/weblens/` | weblens | Fetch blocked/restricted web pages and output readable markdown |
| `plugins/python/` | python | Python build, comments, and testing conventions |
| `plugins/csharp/` | csharp | C# build, comments, and testing conventions |
| `plugins/taskmill-legacy/` | taskmill-legacy | Legacy task management (archived — replaced by mill) |

### Adding a new plugin

1. Create `plugins/<name>/` with a `.claude-plugin/plugin.json` (see existing plugins for reference).
2. Add a `settings.json` in the plugin directory for permissions.
3. Add an entry to `.claude-plugin/marketplace.json` pointing to `./plugins/<name>`.
4. Run `claude plugin install <name>@millhouse` then `.\symlink-plugins.ps1` to link.

### Editing plugins

- Each plugin directory is the source of truth. Edit skills and scripts there directly.
- Plugins are linked via junctions — edits are live immediately. Run `.\symlink-plugins.ps1` if adding a new plugin.

## Git workflow

- Always push immediately after every commit. Never ask — just do it.
- Batch related small changes into one commit. Don't commit trivial edits individually — accumulate doc fixes, settings tweaks, and minor adjustments, then commit them together as one logical unit.

## Kanban

- Backlog board: `_millhouse/backlog.kanban.md` — git-tracked, 3 columns (Backlog, Spawn, Delete). Manual task entry.
- Work board: `_millhouse/scratch/board.kanban.md` — gitignored, 6 phase columns (Discussing, Planned, Implementing, Testing, Reviewing, Blocked). Mill-managed. Each worktree gets its own copy.
- Run `mill-setup` to create both board files after a fresh clone (safe to re-run; skips existing files).
- Format reference: `plugins/mill/doc/modules/kanban-format.md`.
- Work board uses columns as phases — no `[phase]` suffix in task headings.
- Only extension-supported metadata fields (priority, tags, workload, due).
- Descriptions use indented ` ```md ` code blocks, never plain text.
