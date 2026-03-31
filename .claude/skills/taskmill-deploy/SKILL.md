---
description: "Deploy the taskmill plugin by reinstalling it"
---

Reinstall all plugins from the local millhouse marketplace by running the install script.

## Steps

1. Run `bash install-local.sh` from the repo root (`c:/Code/millhouse`).
2. Print the output so the user can see which plugins were installed.

## Fallback

If the script fails, read `.claude-plugin/marketplace.json` and run the install commands manually:

1. `claude plugin marketplace add c:/Code/millhouse`
2. For each plugin: `claude plugin install <name>@millhouse`
3. For each plugin with `requirements.txt`: `pip install -r plugins/<name>/requirements.txt`

Remind the user to restart Claude Code after installation.
