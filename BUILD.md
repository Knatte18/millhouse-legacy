# Build

Instructions for Claude Code. Read this file, then generate the taskmill plugin into `build/taskmill/`.

---

## 1. Read all spec files

Scan `doc/` for:
- All `skill-*.md` files (in any subfolder)
- `doc/taskflow/skill-commands.md` (command specs)
- `doc/taskflow/skill-scripts.md` (script specs)

---

## 2. Generate files into `build/taskmill/`

### Plugin manifest → `build/taskmill/.claude-plugin/plugin.json`

Generate the plugin manifest:

```json
{
  "name": "taskmill",
  "description": "Task management, workflow orchestration, and coding skills for Claude Code",
  "version": "1.0.0",
  "license": "MIT",
  "author": {
    "name": "hanf"
  }
}
```

### All skills → `build/taskmill/skills/<name>/SKILL.md`

Every `skill-*.md` becomes a SKILL.md file in its own directory:

- `skill-<name>.md` → `build/taskmill/skills/<name>/SKILL.md`
- Language subfolders get a prefix: `doc/coding/csharp/skill-comments.md` → `build/taskmill/skills/csharp-comments/SKILL.md`
- **Exception:** `skill-commands.md` and `skill-scripts.md` are not skills — they are sources for commands and scripts.

**Skill files in `doc/` are plugin-ready.** They already contain YAML frontmatter (`name`, `description`) and use `@taskmill:<name>` cross-references. The build step copies each skill file verbatim into its output path — no transformation is applied.

### Commands → `build/taskmill/commands/`

Each `## task-*` or `## mill-*` section in `doc/taskflow/skill-commands.md` → `build/taskmill/commands/<command-name>.md`

```yaml
---
description: "<what the command does>"
argument-hint: "<if applicable>"
---

<complete behavioral spec for this command>
```

- When a command needs skill rules, reference them as: `Use @taskmill:<name> skill`
- Reference scripts as: `python ${CLAUDE_PLUGIN_ROOT}/scripts/<script-name>`

### Scripts → `build/taskmill/scripts/`

Each `## task_*` section in `doc/taskflow/skill-scripts.md` → `build/taskmill/scripts/<script-name>.py`

Implement according to the behavioral spec: parameters, selection priority, output, exit codes.

---

## 3. Marketplace manifest

The file `.claude-plugin/marketplace.json` at the repo root is maintained manually (not generated). It points to `./build/taskmill` as the plugin source.

---

## Result

```
build/taskmill/
├── .claude-plugin/
│   └── plugin.json              (plugin manifest)
├── commands/
│   ├── task-*.md                (one per task command)
│   └── mill-*.md                (one per mill command)
├── skills/
│   ├── conversation/SKILL.md    (core — loads on startup)
│   ├── workflow/SKILL.md        (core — loads on startup)
│   ├── llm-context/SKILL.md     (core — loads on startup)
│   ├── formats/SKILL.md
│   ├── code-quality/SKILL.md
│   ├── cli/SKILL.md
│   ├── linting/SKILL.md
│   ├── git/SKILL.md
│   ├── csharp-build/SKILL.md
│   ├── csharp-comments/SKILL.md
│   └── csharp-testing/SKILL.md
└── scripts/
    └── task_*.py                (one per script)
```

---

## Updating skills

Edit spec files in `doc/`, then run `mill-build` to regenerate into `build/taskmill/`. Then run `mill-deploy` to reinstall the plugin.

By default, the build is **incremental**: it uses `git diff --name-only HEAD -- doc/` to detect changed sources and only regenerates their corresponding outputs. Use `mill-build full` for a complete clean + rebuild.
