---
name: codeguide-maintain
description: "Fix existing docs: content accuracy, structural violations, pointers, links, local-rules. Heavy, scoped."
argument-hint: "[--structure] [project] [module-path]"
---

Sync existing `_codeguide/` documentation with current source code, Documentation Guide, and local rules. Fixes content accuracy, structural compliance, pointer consistency, and link rules. Does **not** commit.

## Modes

- **Full** (default): reads source files and docs. Fixes content accuracy, structure, pointers, links.
- **Structure** (`--structure`): reads docs only, no source. Fixes doc structure against the guide and local rules, Overview tables, link rules, cgexclude entries. Fast — use after updating the guide, local rules, or cgexclude.md.

## When to use

- After code changes that affect module behavior, interfaces, or relationships → full mode
- After adding or changing a rule in `local-rules.md` → `--structure`
- After a plugin update brings a new `DocumentationGuide.md` → `--structure`
- After editing `cgexclude.md` → `--structure`
- As a full audit + fix pass on a project → full mode

## Scope

`$ARGUMENTS` controls what gets synced:

- No argument → all docs in all documented projects
- `MyProject` → all docs in that project's `_codeguide/`
- `MyProject/Storage` → only the Storage subfolder docs
- `MyProject/Storage/BlobCache` → only that one doc file

## Steps

1. **Find `_codeguide/`:** Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/_resolve.py` to locate the nearest `_codeguide/` containing config.yaml. If it exits with an error, stop — run `/codeguide-setup` first.

2. **Read the Documentation Guide:** Read `_codeguide/modules/DocumentationGuide.md` in full. This is the authoritative structure.

3. **Read local rules:** Read `_codeguide/local-rules.md` if it exists.

4. **Read ignore and exclude lists:** Read `_codeguide/cgignore.md` and `_codeguide/cgexclude.md`. Skip paths matching ignore entirely. Skip paths matching exclude for doc checks (but verify they appear in Overview.md).

5. **Determine scope:** Parse `$ARGUMENTS` to identify which project(s) and doc file(s) to sync. If no argument, find all projects that have `_codeguide/Overview.md`.

6. **For each doc in scope:**

   a. **Read the existing doc.**

   b. *(full mode only)* **Read the corresponding source file(s)** to check if behavior, interfaces, or relationships have changed.

   c. *(full mode only)* **Check the Source section:** Verify that the relative paths in the `## Source` section resolve to existing files. If a path is broken, search for the file by name and update the path. If the Source section is missing, add it.

   d. *(full mode only)* **Check doc content against source code:**
      - Stale content (doc describes behavior that no longer matches the code)
      - Code-derived values that should not be in the doc (formulas, thresholds, constants)

   e. **Check doc structure against guide and local rules:**
      - Missing required sections
      - Sections that don't match guide conventions
      - Formatting or structural issues
      - Violations of local rules

   f. **Check link rules:**
      - No sibling links (links to other docs in the same folder)
      - Cross-area links must target Overview.md, not specific module docs

   g. **Update the doc** if any of the above apply. Preserve accurate existing content — only change what's wrong or missing.

7. **Check Overview routing tables:** For each Overview.md in scope:
   - Every `.md` file in `modules/` must have a row in the table
   - Every link in the table must resolve to an existing file
   - Excluded modules (from cgexclude.md) must appear with their description and *excluded* in the Doc column
   - Remove any "not yet documented" placeholder rows — a module either has docs, is excluded, or is not listed
   - Fix any issues found

8. *(full mode only)* **Validate local rules:** For each verifiable rule in `local-rules.md`, spot-check against the code. If there is a mismatch, **stop and ask the user** — is the rule outdated or the code non-conforming? Do not auto-fix.

9. **Report changes:** Summarize what was updated and which rule or code change triggered each fix.

## Parallelism

For large scopes, use parallel subagents — one per project. Each subagent receives the Documentation Guide, local rules, and its project's Overview.md, then processes that project's docs independently. Subagents can further parallelize per module doc if the project is large.

Include the relevant `_codeguide/Overview.md` in every subagent prompt.

## Rules

- Read the Documentation Guide and local rules first — do not rely on memory.
- Do not create new docs for undocumented source files. That is `/codeguide-generate`'s job. Flag undocumented files to the user.
- Do not delete docs. If a doc has no corresponding source, flag it to the user.
- Preserve accurate existing content. Only modify what is structurally wrong or factually stale.
- When updating structure to match the guide, keep the existing content's meaning intact.
