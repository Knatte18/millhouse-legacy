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

### 4. Add routing memories

The plugin hooks inject routing instructions on every turn, but Claude Code can still skip them. Adding feedback memories reinforces the behavior. Add two entries to the target repo's Claude Code memory directory:

**Routing-first lookup** — ALWAYS READ `_codeguide/Overview.md` before using Grep, Glob, or Bash to find files or symbols. Even targeted symbol lookups must go through routing first. Without this, Claude bypasses the routing system with direct searches and misses the documentation layer.

**Source-of-truth verification** — After routing via `_codeguide/`, ALWAYS READ the actual source files before answering factual questions. NEVER answer from doc content alone. Docs can contain stale or incomplete information, so the source code is the authority.

### 5. Enable enforcement (recommended)

Set `enforcement: true` in `_codeguide/config.yaml` (on by default). This activates hooks that block search tools until `_codeguide/Overview.md` has been read. Without enforcement, the routing instructions are advisory only.

Optionally set `violation_logging: true` to log navigation violations to `runtime/navigation-issues.md` for review with `/review-navigation`. Useful during guide development.

---

## Updating

After editing skills, hooks, or templates in `plugins/codeguide/`:

1. Run `./install-local.sh` or `claude plugin install codeguide@millhouse`.
2. Run `/codeguide-setup` in each target repo to update plugin-owned files (DocumentationGuide.md, NavigationHooks.md).
