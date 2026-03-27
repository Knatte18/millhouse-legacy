# Install

How to install the taskmill plugin for Claude Code.

---

## Prerequisites

- [Claude Code](https://claude.com/claude-code) CLI installed and on your PATH.
- Python 3 and pip installed and on your PATH.
- This repository cloned locally (e.g. `c:\Code\taskmill`).

---

## Steps

### 1. Add the marketplace (first time only)

Register this repo as a local plugin marketplace:

```
claude plugin marketplace add c:/Code/taskmill
```

This tells Claude Code where to find `.claude-plugin/marketplace.json`.

### 2. Install the plugin

```
claude plugin install taskmill@taskmill
```

The plugin source is `taskmill/` at the repo root. There is no build step.

### 3. Install Python dependencies

```
pip install -r taskmill/requirements.txt
```

### 4. Start a new session

Close and reopen Claude Code so it picks up the installed plugin.

---

## Updating

After editing skills or scripts in `taskmill/`:

1. `/taskmill-deploy` — reinstalls the plugin.
