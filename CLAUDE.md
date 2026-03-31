# CLAUDE.md
Instructions for Claude Code when working in this repository.

## Background
- This repo is based on a repo by Craig Motlin. When referring to "what Motlin does", I am referring to his code and repo. The repo can be found here: "C:\Code\motlin-claude-code-plugins".

## Repository structure

Millhouse is a multi-plugin marketplace for Claude Code. Each plugin lives in `plugins/<name>/`.

### Plugins

| Directory | Plugin | Description |
|-----------|--------|-------------|
| `plugins/taskmill/` | taskmill | Task management, workflow orchestration, and coding skills |

### Adding a new plugin

1. Create `plugins/<name>/` with a `.claude-plugin/plugin.json` (see `plugins/taskmill/.claude-plugin/plugin.json` for reference).
2. Add a `settings.json` in the plugin directory for permissions.
3. Add an entry to `.claude-plugin/marketplace.json` pointing to `./plugins/<name>`.
4. Run `./install-local.sh` or `/taskmill-deploy` to deploy.

### Editing plugins

- Each plugin directory is the source of truth. Edit skills and scripts there directly.
- To deploy (reinstall all plugins): run `/taskmill-deploy` or `./install-local.sh`.
