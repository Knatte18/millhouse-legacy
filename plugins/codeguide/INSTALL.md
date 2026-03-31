# Install

How to install the codeguide plugin for Claude Code.

---

## Prerequisites

- [Claude Code](https://claude.com/claude-code) CLI installed and on your PATH.
- Python 3 installed and on your PATH.
- This repository cloned locally (e.g. `c:\Code\millhouse`).

---

## Steps

### 1. Install from millhouse marketplace

```
./install-local.sh
```

This installs all millhouse plugins globally, including codeguide.

Or install codeguide individually:

```
claude plugin marketplace add c:/Code/millhouse
claude plugin install codeguide@millhouse
```

### 2. Restart Claude Code

Close and reopen Claude Code so it picks up the plugin.

### 3. Set up the documentation skeleton

From the target repo:

```
/codeguide-setup .cs .py
```

This creates the `_codeguide/` directory with config, templates, and runtime folders.

---

## Updating

After editing skills or templates in `plugins/codeguide/`:

1. Run `./install-local.sh` or `claude plugin install codeguide@millhouse`.
2. Run `/codeguide-setup` in each target repo to update plugin-owned files (DocumentationGuide.md, NavigationHooks.md).
