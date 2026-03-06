---
description: "Deploy built skills by reinstalling the taskmill plugin"
---

## Behavior

Reinstall the taskmill plugin from the local marketplace.

### Steps

1. Run `claude plugin uninstall taskmill@taskmill` (ignore errors if not yet installed).
2. Run `claude plugin install taskmill@taskmill`.
3. Print confirmation that the plugin was reinstalled.

### First-time setup

If the marketplace has not been added yet:

1. Run `claude plugin marketplace add c:/Code/taskmill` (the repo root containing `.claude-plugin/marketplace.json`).
2. Then proceed with install as above.

### Fallback

If `claude` is not found on PATH, try `npx @anthropic-ai/claude-code` instead. If that also fails, print the commands for the user to run manually and explain they need `claude` CLI available.

Remind the user to restart Claude Code after installation.
