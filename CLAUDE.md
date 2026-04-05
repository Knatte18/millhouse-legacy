# CLAUDE.md
Instructions for Claude Code when working in this repository.

## Background
- This repo is based on a repo by Craig Motlin. When referring to "what Motlin does", I am referring to his code and repo. The repo can be found here: "C:\Code\motlin-claude-code-plugins".

## Repository structure

Millhouse is a multi-plugin marketplace for Claude Code. Each plugin lives in `plugins/<name>/`.

### Plugins

| Directory | Plugin | Description |
|-----------|--------|-------------|
| `plugins/taskmill/` | taskmill | Task management and workflow orchestration (legacy — being replaced by helm) |
| `plugins/codeguide/` | codeguide | Navigation-first documentation system for AI-assisted codebases |
| `plugins/conduct/` | conduct | Response style, behavior rules, skill routing, language detection |
| `plugins/helm/` | helm | Worktree-based task orchestration |
| `plugins/weblens/` | weblens | Fetch blocked/restricted web pages and output readable markdown |
| `plugins/code/` | code | Code quality, CLI, linting, and testing standards |
| `plugins/git/` | git | Git workflow rules, commit, issue creation |
| `plugins/python/` | python | Python build, comments, and testing conventions |
| `plugins/csharp/` | csharp | C# build, comments, and testing conventions |

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

- Backlog board: `kanbans/backlog.kanban.md` — git-tracked, 3 columns (Backlog, Spawn, Delete). Manual task entry.
- Work board: `kanbans/board.kanban.md` — gitignored, 6 phase columns (Discussing, Planned, Implementing, Testing, Reviewing, Blocked). Helm-managed. Each worktree gets its own copy.
- Run `helm-setup` to create both board files after a fresh clone (safe to re-run; skips existing files).
- Format reference: `plugins/helm/doc/modules/kanban-format.md`.
- Work board uses columns as phases — no `[phase]` suffix in task headings.
- Only extension-supported metadata fields (priority, tags, workload, due).
- Descriptions use indented ` ```md ` code blocks, never plain text.
