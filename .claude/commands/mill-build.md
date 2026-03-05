---
description: "Build skills from doc/ specs into build/"
argument-hint: "full"
---

Read and follow BUILD.md

## Behavior

Generate skill files from `doc/` into `build/`. Follow the rules in BUILD.md exactly.

### Default (incremental)

1. Run `git diff --name-only HEAD -- doc/` to find changed source files.
2. Map each changed file to its build output(s):
   - `doc/**/skill-*.md` (except skill-commands.md and skill-scripts.md) → `build/skills/<name>.md`
   - `doc/taskflow/skill-commands.md` → all files in `build/commands/`
   - `doc/taskflow/skill-scripts.md` → all files in `build/scripts/`
3. Only regenerate the affected output files. Leave unchanged outputs alone.
4. If no doc/ files changed, print "Nothing to rebuild" and stop.
5. Print a summary of regenerated files.

### Full rebuild (`full` argument)

1. Clean `build/skills/`, `build/commands/`, `build/scripts/` (remove all generated files, keep `.gitkeep`).
2. Read all spec files under `doc/`.
3. Generate into `build/` following BUILD.md rules:
   - Skills → `build/skills/`
   - Commands → `build/commands/`
   - Scripts → `build/scripts/`
   - CLAUDE.md → `build/CLAUDE.md`
4. Print a summary of generated files.
