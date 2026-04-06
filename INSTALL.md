# Install

## Prerequisites

- [Claude Code](https://claude.com/claude-code) CLI installed and on your PATH.
- This repository cloned locally (e.g. `c:\Code\millhouse`).

## Install (two steps)

### Step 1: Register marketplace and install plugins

```
claude plugin marketplace add c:/Code/millhouse
claude plugin install mill@millhouse
claude plugin install python@millhouse
claude plugin install csharp@millhouse
```

Optional:
```
claude plugin install weblens@millhouse
```

### Step 2: Link plugins to source

From the millhouse repo root (PowerShell):

```powershell
.\symlink-plugins.ps1
```

This replaces the plugin cache with junctions to your local source. Edits in `plugins/` are live immediately — no deploy step needed.

Weblens requires Node.js dependencies:
```powershell
cd plugins\weblens
npm install
```

## Per-repo setup

Run inside the target repo after global install:

```
/mill-setup
```

This creates the `_millhouse/` directory, kanban boards, config, and forwarding wrapper scripts.

## Updating

Symlinks mean edits in `plugins/` are live immediately. No deploy needed.

Re-run `.\symlink-plugins.ps1` only if you add a new plugin or reinstall Claude Code.
