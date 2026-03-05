---
description: "Deploy built skills to ~/.claude/ (or specified target)"
argument-hint: "[target-path]"
---

## Behavior

Copy all generated files from `build/` to the deploy target.

- Default target: `~/.claude/` (global install)
- Optional argument: a target path (e.g., a project's `.claude/` directory)

### Steps

1. Determine target: use argument if provided, otherwise `~/.claude/`.
2. Copy `build/skills/*` → `<target>/skills/`
3. Copy `build/commands/*` → `<target>/commands/`
4. Copy `build/scripts/*` → `<target>/scripts/`
5. Read `build/CLAUDE.md`. Ensure its content is present in `<target>/CLAUDE.md`:
   - If `<target>/CLAUDE.md` does not exist, create it with the content.
   - If it exists, check whether the core skill references are already present. If not, append them.
6. Print a summary of deployed files and the target path.
