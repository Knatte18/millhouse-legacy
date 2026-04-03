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
- Never commit kanban files alone. Stage `kanbans/` changes with the next code commit.
- Batch related small changes into one commit. Don't commit trivial edits individually — accumulate doc fixes, settings tweaks, and minor adjustments, then commit them together as one logical unit.

## Kanban

- Task boards: `kanbans/` directory with 4 separate board files (kanban.md VS Code extension).
  - `kanbans/backlog.kanban.md`, `kanbans/processing.kanban.md`, `kanbans/done.kanban.md`, `kanbans/blocked.kanban.md`
- Format reference: `plugins/helm/doc/modules/kanban-format.md`.
- Tasks use `### Title [phase]` headings. Only extension-supported metadata fields (priority, tags, workload, due).
- Descriptions use indented ` ```md ` code blocks, never plain text.
