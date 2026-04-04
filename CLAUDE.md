# CLAUDE.md
Instructions for Claude Code when working in this repository.

## Background
- This repo is based on a repo by Craig Motlin. When referring to "what Motlin does", I am referring to his code and repo. The repo can be found here: "C:\Code\motlin-claude-code-plugins".

## Repository structure

Millhouse is a multi-plugin marketplace for Claude Code. Each plugin lives in `plugins/<name>/`.

### Plugins

| Directory | Plugin | Description |
|-----------|--------|-------------|
| `plugins/taskmill/` | taskmill | Task management and workflow orchestration |
| `plugins/codeguide/` | codeguide | Navigation-first documentation system for AI-assisted codebases |
| `plugins/conduct/` | conduct | Response style, behavior rules, skill routing, language detection |
| `plugins/helm/` | helm | Worktree-based task orchestration (in design — see `plugins/helm/doc/`) |
| `plugins/weblens/` | weblens | Fetch blocked/restricted web pages and output readable markdown |
| `plugins/code/` | code | Code quality, CLI, linting, and testing standards |
| `plugins/git/` | git | Git workflow rules |
| `plugins/python/` | python | Python build, comments, and testing conventions |
| `plugins/csharp/` | csharp | C# build, comments, and testing conventions |

### Adding a new plugin

1. Create `plugins/<name>/` with a `.claude-plugin/plugin.json` (see `plugins/taskmill/.claude-plugin/plugin.json` for reference).
2. Add a `settings.json` in the plugin directory for permissions.
3. Add an entry to `.claude-plugin/marketplace.json` pointing to `./plugins/<name>`.
4. Run `/taskmill-deploy` to deploy, or re-run the install commands from `INSTALL.md`.

### Editing plugins

- Each plugin directory is the source of truth. Edit skills and scripts there directly.
- Plugins are linked via junctions/symlinks — edits are live immediately. Run `.\symlink-plugins.ps1` if adding a new plugin.

## Git workflow

- Always push immediately after every commit. Never ask — just do it.
