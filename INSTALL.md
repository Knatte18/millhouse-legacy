# Install

How to install plugins from the millhouse marketplace for Claude Code.

---

## Prerequisites

- [Claude Code](https://claude.com/claude-code) CLI installed and on your PATH.
- Python 3 and pip installed and on your PATH.
- This repository cloned locally (e.g. `c:\Code\millhouse`).

---

## Quick install (all plugins)

```
./install-local.sh
```

This registers the marketplace and installs all plugins listed in `.claude-plugin/marketplace.json`.

---

## Manual steps

### 1. Add the marketplace (first time only)

```
claude plugin marketplace add c:/Code/millhouse
```

### 2. Install a plugin

```
claude plugin install taskmill@millhouse
```

### 3. Install Python dependencies (if needed)

```
pip install -r plugins/taskmill/requirements.txt
```

### 4. Start a new session

Close and reopen Claude Code so it picks up the installed plugin.

---

## Updating

After editing skills or scripts in `plugins/`:

1. `/taskmill-deploy` — reinstalls all plugins.
2. Or run `./install-local.sh` directly.
