---
name: mill-skills-index
description: Regenerate SKILLS.md (repo root) and per-plugin INDEX.md from SKILL.md frontmatter. Manual invocation only — no pre-commit hook.
---

# mill-skills-index

Regenerate the skill indices by scanning `plugins/*/skills/**/SKILL.md` for YAML frontmatter (`name:` and `description:`), then writing:

- `SKILLS.md` at the repo root (combined table across all plugins)
- `plugins/<plugin>/skills/INDEX.md` for each plugin (scoped table)

The scanner is deterministic — sorted alphabetically by skill name, `\n`-only line endings, trailing newline. Re-running produces byte-identical output.

## Usage

```
/mill-skills-index
```

## Steps

1. **Locate the entrypoint.** Resolve `skills_index.py` via three-tier resolution:
   - `_millhouse/skills-index.py` forwarding wrapper (if present)
   - `<repo-root>/plugins/mill/scripts/millpy/entrypoints/skills_index.py` (in-repo plugin source)
   - `~/.claude/plugins/cache/millhouse/mill/<latest-version>/scripts/millpy/entrypoints/skills_index.py` (plugin cache)

2. **Run the scanner.**

   ```bash
   PYTHONPATH=plugins/mill/scripts python -m millpy.entrypoints.skills_index
   ```

3. **Parse stdout.** The entrypoint prints a one-line summary followed by the list of written file paths. Relay that list to the user.

4. **Stage and commit** the generated files:

   ```bash
   git add SKILLS.md plugins/*/skills/INDEX.md
   git commit -m "chore: regenerate skill indices"
   git push
   ```

## Rules

- Missing or malformed frontmatter on any SKILL.md emits a warning to stderr and skips that file — the scanner never raises.
- The skill is manual-only. No pre-commit hook, no auto-fire.
- The frontmatter is the source of truth; the indices are a view. Do not hand-edit `SKILLS.md` or `INDEX.md` — edit the underlying `SKILL.md` files and regenerate.
