---
description: "Build skills from doc/ specs into build/"
argument-hint: "full"
---

Read and follow BUILD.md

## Behavior

Generate the taskmill plugin from `doc/` into `build/taskmill/`. Follow the rules in BUILD.md exactly.

### Default (incremental)

1. Run `git diff --name-only HEAD -- doc/` to find changed source files.
2. Map each changed file to its build output(s):
   - `doc/**/skill-*.md` (except skill-commands.md and skill-scripts.md) → `build/taskmill/skills/<name>/SKILL.md`
   - `doc/taskflow/skill-commands.md` → all files in `build/taskmill/commands/`
   - `doc/taskflow/skill-scripts.md` → all files in `build/taskmill/scripts/`
3. Only regenerate the affected output files. Leave unchanged outputs alone.
4. If no doc/ files changed, print "Nothing to rebuild" and stop.
5. Print a summary of regenerated files.

### Full rebuild (`full` argument)

1. Clean `build/taskmill/` (remove all generated files under skills/, commands/, scripts/, keep `.claude-plugin/plugin.json`).
2. Read all spec files under `doc/`.
3. Generate into `build/taskmill/` following BUILD.md rules:
   - Plugin manifest → `build/taskmill/.claude-plugin/plugin.json`
   - Skills → `build/taskmill/skills/<name>/SKILL.md`
   - Commands → `build/taskmill/commands/`
   - Scripts → `build/taskmill/scripts/`
4. Print a summary of generated files.
