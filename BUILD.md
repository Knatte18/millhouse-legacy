# Build

Instructions for Claude Code. Read this file, then generate the taskmill plugin into `build/taskmill/`.

---

## 1. Read all spec files

Scan `doc/` for:
- All `skill-*.md` files (in any subfolder)
- `doc/taskflow/skill-scripts.md` (script specs)

**Note:** `doc/taskflow/skill-commands.md` is a human-readable reference only — it does not drive the build. Command source files are `doc/taskflow/skill-<name>.md`.

---

## 2. Generate files into `build/taskmill/`

### Plugin manifest → `build/taskmill/.claude-plugin/plugin.json`

Generate the plugin manifest:

```json
{
  "name": "taskmill",
  "description": "Task management, workflow orchestration, and coding skills for Claude Code",
  "version": "1.0.0",
  "license": "Apache-2.0",
  "author": {
    "name": "Knatte18"
  }
}
```

### All skills → `build/taskmill/skills/<name>/SKILL.md`

Every `skill-*.md` becomes a SKILL.md file in its own directory:

- `skill-<name>.md` → `build/taskmill/skills/<name>/SKILL.md`
- Language subfolders get a prefix: `doc/coding/csharp/skill-comments.md` → `build/taskmill/skills/csharp-comments/SKILL.md`
- **Exception:** `skill-scripts.md` is not a skill — it is the source for scripts. `skill-commands.md` is a reference doc and is also excluded.

**Skill files in `doc/` are plugin-ready.** They already contain YAML frontmatter (`name`, `description`) and use `@taskmill:<name>` cross-references. The build step copies each skill file verbatim into its output path — no transformation is applied.

### Scripts → `build/taskmill/scripts/`

`doc/taskflow/skill-scripts.md` defines a `lib/` package and thin CLI wrappers.

**Shared library:** Each `### lib/<module>.py` section → `build/taskmill/scripts/lib/<module>.py`. Also generate `build/taskmill/scripts/lib/__init__.py` (empty file).

**CLI scripts:** Each `### <script>.py` section under `## CLI scripts` → `build/taskmill/scripts/<script>.py`. Implement as thin wrappers that import from `lib.*` and follow the behavioral spec (parameters, selection priority, output, exit codes).

### Hooks → `build/taskmill/hooks/`

Copy `doc/taskflow/hooks.json` → `build/taskmill/hooks/hooks.json` verbatim.
Copy `doc/taskflow/validate-protected-files.sh` → `build/taskmill/hooks/validate-protected-files.sh` verbatim.
Copy `doc/taskflow/validate-git.sh` → `build/taskmill/hooks/validate-git.sh` verbatim.

---

## 3. Marketplace manifest

The file `.claude-plugin/marketplace.json` at the repo root is maintained manually (not generated). It points to `./build/taskmill` as the plugin source.

---

## Result

```
build/taskmill/
├── .claude-plugin/
│   └── plugin.json              (plugin manifest)
├── skills/
│   ├── conversation/SKILL.md    (core — loads on startup)
│   ├── workflow/SKILL.md        (core — loads on startup)
│   ├── llm-context/SKILL.md     (core — loads on startup)
│   ├── formats/SKILL.md
│   ├── code-quality/SKILL.md
│   ├── cli/SKILL.md
│   ├── testing/SKILL.md
│   ├── linting/SKILL.md
│   ├── git/SKILL.md
│   ├── csharp-build/SKILL.md
│   ├── csharp-comments/SKILL.md
│   ├── csharp-testing/SKILL.md
│   ├── python-build/SKILL.md
│   ├── python-comments/SKILL.md
│   ├── python-testing/SKILL.md
│   ├── discuss/SKILL.md         (command skills — verbatim from doc/taskflow/)
│   ├── finalize/SKILL.md
│   ├── do/SKILL.md
│   ├── do-commit/SKILL.md
│   ├── do-all/SKILL.md
│   ├── finalize-do/SKILL.md
│   ├── finalize-do-commit/SKILL.md
│   ├── finalize-do-all/SKILL.md
│   ├── commit/SKILL.md
│   ├── list/SKILL.md
│   ├── add/SKILL.md
│   ├── add-discuss/SKILL.md
│   ├── log/SKILL.md
│   └── retry/SKILL.md
├── scripts/
│   ├── lib/
│   │   ├── __init__.py          (empty — makes lib a package)
│   │   ├── state.py             (CHECKBOX_RE, change_state, is_incomplete)
│   │   ├── parsing.py           (read_lines, find_task, extract_block, delete_block, etc.)
│   │   ├── subbullet.py         (upsert_subbullet)
│   │   ├── locking.py           (get_lock, locked context manager)
│   │   ├── io.py                (write_file, is_backlog)
│   │   ├── backlog_format.py    (normalize_backlog)
│   │   └── frontmatter.py       (find_frontmatter, upsert_frontmatter_key)
│   ├── task_get.py              (thin CLI wrappers)
│   ├── task_add.py
│   ├── task_complete.py
│   ├── task_block.py
│   ├── task_subbullet.py
│   ├── task_claim.py
│   ├── task_plan.py
│   └── plan_finish.py
└── hooks/
    ├── hooks.json               (PreToolUse hook config — copied from doc/taskflow/)
    ├── validate-protected-files.sh (blocks direct edits to backlog.md and plan files — copied from doc/taskflow/)
    └── validate-git.sh          (blocks dangerous git commands — copied from doc/taskflow/)
```

---

## Updating skills

Edit spec files in `doc/`, then run `mill-build` to regenerate into `build/taskmill/`. Then run `mill-deploy` to reinstall the plugin.

By default, the build is **incremental**: it uses `git diff --name-only HEAD -- doc/` to detect changed sources and only regenerates their corresponding outputs. Use `mill-build full` for a complete clean + rebuild.
