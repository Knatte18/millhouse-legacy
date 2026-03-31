---
name: codeguide-update
description: "Update docs for recently changed source files. Default: current git diff. Lightweight, safe for commit-time use."
argument-hint: "[1h | 3d | HEAD~3 | file1 file2 ...]"
---

Update `_codeguide/` docs for source files that changed recently. Designed to be fast and non-intrusive — only touches docs for files in scope. Does **not** commit.

## Scope

`$ARGUMENTS` controls which source files are in scope:

- No argument → files in the current git diff (staged + unstaged). This is the default when called by mill-commit.
- `1h`, `3d`, `2w` → files with git commits in the last hour / 3 days / 2 weeks
- `HEAD~3` → files changed in the last 3 commits
- Explicit file/folder paths → only those

## Steps

1. **Find `_codeguide/`:** Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/_resolve.py` to locate the nearest `_codeguide/` containing config.yaml. If not found, stop — codeguide is not initialized.

2. **Read config:** Load source extensions from `_codeguide/config.yaml`. Filter scope to recognized source files only.

3. **Read cgignore.md and cgexclude.md:** Skip files matching ignore or exclude patterns.

4. **Read the Documentation Guide:** Read `_codeguide/modules/DocumentationGuide.md`.

5. **Read local rules:** Read `_codeguide/local-rules.md` if it exists.

6. **For each source file in scope:**

   a. Find the corresponding doc using the guide's naming rules (two-step lookup via Overview.md).

   b. **If doc exists:** Read the doc and the source file. If the doc is stale or inaccurate, update it. Preserve accurate content.

   c. **If no doc exists and not in cgexclude:** Create it following the guide structure. Update the project Overview.md module table.

   d. **If source was deleted** (only applies to git diff scope): Flag the orphan doc to the user. Do not delete it.

7. **Update Overview routing tables** if any docs were added or if routing hints changed.

8. **Report** what was updated, created, or flagged.

## Rules

- Read the Documentation Guide and local rules first — do not rely on memory.
- Do not touch docs outside the scope.
- Do not include API signatures, code-derived values, or line-by-line walkthroughs.
- Do not commit. The caller (user or mill-commit) decides when to commit.
