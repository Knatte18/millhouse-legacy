# Install

## Prerequisites

- [Claude Code](https://claude.com/claude-code) CLI installed and on your PATH.
- This repository cloned locally (e.g. `c:\Code\millhouse`).

## Install (two steps)

### Step 1: Register marketplace and install plugins

```
claude plugin marketplace add c:/Code/millhouse
claude plugin install taskmill@millhouse
claude plugin install codeguide@millhouse
claude plugin install conduct@millhouse
claude plugin install code@millhouse
claude plugin install git@millhouse
claude plugin install python@millhouse
claude plugin install csharp@millhouse
```

### Step 2: Symlink plugins to source

From the millhouse repo root:

```bash
bash install-plugins.sh
```

This replaces the plugin cache with symlinks to your local source. Edits in `plugins/` are live immediately — no deploy step needed.

Taskmill requires Python dependencies (will be removed when Helm replaces taskmill):
```
pip install -r c:/Code/millhouse/plugins/taskmill/requirements.txt
```

## Per-repo setup

Run these inside the target repo after global install:

- **codeguide:** `/codeguide-setup .py .cs` (adjust extensions for your project)
- **helm:** `/helm-setup` (when available)

## Updating

Symlinks mean edits in `plugins/` are live immediately. No deploy needed.

Re-run `bash install-plugins.sh` only if you add a new plugin or reinstall Claude Code.
