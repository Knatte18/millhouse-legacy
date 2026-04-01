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

This registers the marketplace and installs all plugins globally:

| Plugin | Description |
|--------|-------------|
| taskmill | Task management and workflow orchestration |
| codeguide | Navigation-first documentation system |
| orchestration | Conversation style and LLM context rules |
| code | Code quality, CLI, linting, and testing standards |
| git | Git workflow rules |
| python | Python build, comments, and testing conventions |
| csharp | C# build, comments, and testing conventions |

---

## Manual steps

### 1. Add the marketplace (first time only)

```
claude plugin marketplace add c:/Code/millhouse
```

### 2. Install plugins

```
claude plugin install taskmill@millhouse
claude plugin install codeguide@millhouse
```

### 3. Install Python dependencies

```
pip install -r plugins/taskmill/requirements.txt
```

### 4. Start a new session

Close and reopen Claude Code so it picks up the installed plugins.

---

## Per-repo setup

Some plugins require per-repo initialization after global install:

- **codeguide:** Run `/codeguide-setup .py .cs` in the target repo to create the `_codeguide/` skeleton.

---

## Updating

After editing skills or scripts in `plugins/`:

1. `/taskmill-deploy` — reinstalls all plugins.
2. Or run `./install-local.sh` directly.
