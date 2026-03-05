# Build

Instructions for Claude Code. Read this file, then generate skills into `build/`.

---

## 1. Read all spec files

Scan `doc/` for:
- All `skill-*.md` files (in any subfolder)
- `doc/taskflow/skill-commands.md` (command specs)
- `doc/taskflow/skill-scripts.md` (script specs)

---

## 2. Generate files into `build/`

### All skills → `build/skills/`

Every `skill-*.md` becomes a file in `build/skills/`:

- `skill-<name>.md` → `build/skills/<name>.md`
- Language subfolders get a prefix: `doc/coding/csharp/skill-comments.md` → `build/skills/csharp-comments.md`
- **Exception:** `skill-commands.md` and `skill-scripts.md` are not skills — they are sources for commands and scripts.
- Copy content as-is. No frontmatter needed.

### CLAUDE.md → reference core skills

Generate `build/CLAUDE.md` containing:

```markdown
Always read and follow these skill files:
- ~/.claude/skills/conversation.md
- ~/.claude/skills/llm-context.md
- ~/.claude/skills/workflow.md
```

This ensures the core skills (response style, directory structure, workflow) are active in every session.

### Commands → `build/commands/`

Each `## task-*` or `## mill-*` section in `doc/taskflow/skill-commands.md` → `build/commands/<command-name>.md`

```yaml
---
description: "<what the command does>"
argument-hint: "<if applicable>"
---

<complete behavioral spec for this command>
```

- When a command needs skill rules, tell CC to read the relevant file: `Read and follow ~/.claude/skills/<name>.md`
- Reference scripts as: `python ~/.claude/scripts/<script-name>`

### Scripts → `build/scripts/`

Each `## task_*` section in `doc/taskflow/skill-scripts.md` → `build/scripts/<script-name>.py`

Implement according to the behavioral spec: parameters, selection priority, output, exit codes.

---

## Result

```
build/
├── CLAUDE.md                (references core skills)
├── commands/
│   └── task-*.md            (one per command)
│   └── mill-*.md            (one per mill command)
├── skills/
│   └── *.md                 (all skills, including core)
└── scripts/
    └── task_*.py            (one per script)
```

---

## Updating skills

Edit spec files in `doc/`, then run `mill-build` to regenerate into `build/`. Then run `mill-deploy` to deploy to `~/.claude/`.

By default, the build is **incremental**: it uses `git diff --name-only HEAD -- doc/` to detect changed sources and only regenerates their corresponding outputs. Use `mill-build full` for a complete clean + rebuild.
