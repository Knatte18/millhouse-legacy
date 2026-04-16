---
name: codeguide-setup
description: "Set up, refresh, or activate codeguide. Detects context automatically: first-time root, refresh, or subfolder."
argument-hint: "[.cs .py .ts]"
---

Set up or refresh codeguide in the current working directory. Detects context automatically. Does **not** commit.

## What this creates (first-time root)

```
_codeguide/
├── config.yaml                    ← source file extensions (you own this)
├── local-rules.md                 ← repo-specific doc rules (you own this)
├── Overview.md                    ← repo routing table (you own this)
├── cgignore.md                    ← system-level ignores (plugin-owned)
├── cgexclude.md                   ← module exclusions (you own this)
├── NavigationHooks.md             ← hook reference (plugin-owned)
└── modules/
    └── DocumentationGuide.md      ← how to write docs (plugin-owned)
```

## Steps

1. **Detect context:** Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/millpy/codeguide/resolve.py` to find the nearest `_codeguide/` with config.yaml.

2. **Determine mode:**
   - Config.yaml not found anywhere → **first-time root setup**
   - Config.yaml is in cwd's own `_codeguide/` → **root refresh**
   - Config.yaml is in an ancestor's `_codeguide/`, and cwd has `_codeguide/root.txt` → **subfolder refresh**
   - Config.yaml is in an ancestor's `_codeguide/`, and either cwd has no `_codeguide/` OR cwd's `_codeguide/` has no `root.txt` → **new subfolder** — report what was found and ask user to confirm before proceeding. (The second case covers half-manual state where an earlier workflow created `_codeguide/Overview.md` or `_codeguide/modules/` without registering the folder as a subfolder workspace.)

---

### First-time root setup

3. **Check prerequisites:** Verify the working directory is a git repo (`.git/` exists). If not, stop with an error.

4. **Read plugin files** from `${CLAUDE_PLUGIN_ROOT}`:
   - `templates/DocumentationGuide.md`
   - `templates/config.yaml`
   - `templates/local-rules.md`
   - `templates/cgignore.md`
   - `templates/cgexclude.md`
   - `hooks/NavigationHooks.md`

5. **Create directories:** Create `_codeguide/modules/`.

6. **Copy plugin-owned files:**
   - `templates/DocumentationGuide.md` → `_codeguide/modules/DocumentationGuide.md`
   - `hooks/NavigationHooks.md` → `_codeguide/NavigationHooks.md`

7. **Create user-owned files** (only if they don't exist):
   - `_codeguide/cgignore.md` — copy from template (user adds repo-specific entries).
   - `_codeguide/config.yaml` — if `$ARGUMENTS` contains extensions (args starting with `.`), write a config with those extensions. Otherwise copy the template.
   - `_codeguide/local-rules.md` — copy from template.
   - `_codeguide/cgexclude.md` — copy from template.
   - `_codeguide/Overview.md` — create with starter content:
     ```markdown
     # Repo Overview

     TODO: Add a project map table and dependency graph.

     ## Documentation system

     See [DocumentationGuide.md](modules/DocumentationGuide.md) for how docs are written and organized.

     See [NavigationHooks.md](NavigationHooks.md) for routing enforcement.
     ```

8. **Report** what was created.

---

### Root refresh

3. **Read plugin source files** from `${CLAUDE_PLUGIN_ROOT}`:
   - `templates/DocumentationGuide.md`
   - `hooks/NavigationHooks.md`
   - `templates/config.yaml`

4. **Overwrite plugin-owned files:**
   - `_codeguide/modules/DocumentationGuide.md`
   - `_codeguide/NavigationHooks.md`

5. **Merge config schema:** For each key in the template that is missing from the repo's `_codeguide/config.yaml`, add it with its default value and comment. Do not change existing values.

6. **Create `_codeguide/cgexclude.md`** if it doesn't exist.

7. **Report** what was updated.

---

### Subfolder refresh

3. **Update `_codeguide/root.txt`** with the current resolved path.

4. **Create `_codeguide/cgexclude.md`** if it doesn't exist.

5. **Report** what was updated.

---

### New subfolder activation

3. **Report findings:** "Found repo-level `_codeguide/` at `<path>`." If cwd already has a `_codeguide/` directory without `root.txt`, add: "cwd already has `_codeguide/` with files: `<list>`. Promote this folder to a subfolder workspace without touching existing files?" Otherwise: "Set up this folder as a subfolder workspace?"

4. **Wait for user confirmation.** If denied, stop.

5. **Create `_codeguide/` directory** if it does not exist. If it already exists, leave existing files untouched — this step is the promote case.

6. **Create `_codeguide/root.txt`** with the resolved path to the ancestor `_codeguide/`.

7. **Create `_codeguide/cgexclude.md`** from template — only if it does not already exist.

8. **Report** what was created (distinguish "created new subfolder workspace" vs "promoted existing `_codeguide/` to subfolder workspace", listing which files were touched).

## Rules

- Do not overwrite user-owned files: config.yaml values, local-rules.md, cgexclude.md, Overview.md, module docs.
- Do not commit. The user decides when to commit.
- Safe to re-run in any mode. Plugin-owned files are refreshed, user-owned files are preserved.
