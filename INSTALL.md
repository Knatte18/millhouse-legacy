# Install

How to build and install the taskmill plugin for Claude Code.

---

## Prerequisites

- [Claude Code](https://claude.com/claude-code) CLI installed and on your PATH.
- This repository cloned locally (e.g. `c:\Code\taskmill`).

---

## Steps

### 1. Build the plugin

From within the repo, run the `/mill-build full` command in Claude Code. This reads every spec file under `doc/` and generates the plugin into `build/taskmill/`.

```
/mill-build full
```

After the build finishes, verify that `build/taskmill/` contains:

```
build/taskmill/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   ├── task-*.md
│   └── mill-*.md
├── skills/
│   └── <name>/SKILL.md   (one per skill)
└── scripts/
    └── task_*.py
```

### 2. Add the marketplace (first time only)

Register this repo as a local plugin marketplace:

```
claude plugin marketplace add c:/Code/taskmill
```

This tells Claude Code where to find `.claude-plugin/marketplace.json`.

### 3. Install the plugin

```
claude plugin install taskmill@taskmill
```

### 4. Remove old flat-structure files (if upgrading)

If you previously used the non-plugin version, remove the old files to avoid duplicates:

```
rm ~/.claude/skills/cli.md
rm ~/.claude/skills/code-quality.md
rm ~/.claude/skills/conversation.md
rm ~/.claude/skills/csharp-build.md
rm ~/.claude/skills/csharp-comments.md
rm ~/.claude/skills/csharp-testing.md
rm ~/.claude/skills/formats.md
rm ~/.claude/skills/git.md
rm ~/.claude/skills/linting.md
rm ~/.claude/skills/llm-context.md
rm ~/.claude/skills/workflow.md
rm ~/.claude/commands/mill-commit.md
rm ~/.claude/commands/task-add.md
rm ~/.claude/commands/task-discuss.md
rm ~/.claude/commands/task-do.md
rm ~/.claude/commands/task-do-all.md
rm ~/.claude/commands/task-list.md
rm ~/.claude/commands/task-plan.md
rm ~/.claude/commands/task-retry.md
rm ~/.claude/scripts/task_add.py
rm ~/.claude/scripts/task_block.py
rm ~/.claude/scripts/task_claim.py
rm ~/.claude/scripts/task_complete.py
rm ~/.claude/scripts/task_get.py
rm ~/.claude/scripts/task_lock.py
```

### 5. Start a new session

Close and reopen Claude Code so it picks up the installed plugin.

---

## Updating

After editing specs in `doc/`:

1. `/mill-build` — incremental rebuild (only changed files).
2. `/mill-deploy` — reinstalls the plugin.

Use `/mill-build full` for a clean rebuild of everything.
