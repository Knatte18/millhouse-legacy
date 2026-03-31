---
name: codeguide-generate
description: "Generate _codeguide/ documentation for source files that have no docs yet. Works for new and existing projects."
argument-hint: "[project] [module-path]"
---

Generate `_codeguide/` documentation for source files that don't have corresponding docs. Works both for projects with no docs at all and for existing projects with new source files. Does **not** commit.

## Scope

`$ARGUMENTS` controls what gets scanned:

- No argument → all projects in the repo
- `MyProject` → only that project
- `MyProject/Storage` → only that subfolder

## Steps

1. **Find `_codeguide/`:** Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/_resolve.py` to locate the nearest `_codeguide/` containing config.yaml. If it exits with an error, stop — run `/codeguide-setup` first.

2. **Read the Documentation Guide:** Read `_codeguide/modules/DocumentationGuide.md` in full. All docs must follow its structure.

3. **Read local rules:** Read `_codeguide/local-rules.md` if it exists.

4. **Read config and filters:**
   - Read `_codeguide/config.yaml` for recognized source extensions.
   - Read `_codeguide/cgignore.md` — skip these paths entirely.
   - Read `_codeguide/cgexclude.md` — skip these modules (but ensure they appear in Overview.md with a brief description).

5. **Scan source structure:** List all folders and source files matching recognized extensions in scope, skipping paths that match cgignore patterns.

6. **Identify undocumented source:** For each source file or source folder, check if a corresponding doc exists using the naming rules from the guide:
   - `parser.py` → `_codeguide/modules/Parser.md`
   - `utils/` (folder) → `_codeguide/modules/Utils.md`
   - If the doc exists and is current, skip it.
   - If the source matches a cgexclude pattern, skip doc creation.

7. **Read undocumented source files:** Read only the source files that need new docs. Use parallel agent reads for large sets.

8. **Decide doc granularity:** Following the guide's rules:
   - One doc per source file or source folder
   - Large modules with subfolders get their own `_codeguide/modules/<Module>/Overview.md` + per-file docs
   - Small modules get a flat `_codeguide/modules/<Name>.md`

9. **Create docs for new project (if no Overview exists):**
   - Create `_codeguide/` and `_codeguide/modules/`
   - Write `_codeguide/Overview.md` with: scope, negative boundaries, dependencies, module table with routing hints, cross-cutting patterns
   - Include excluded modules (from cgexclude.md) in the Overview table with their description from cgexclude. Mark them as *excluded* in the Doc column. Do not add "not yet documented" placeholders.
   - Update the repo-level `_codeguide/Overview.md` project table

10. **Write module docs:** For each undocumented module, create the doc following the guide structure:
    - What and why
    - Capability summaries (plain language, no signatures)
    - When not to use (negative space)
    - Relationships (depends on, consumed by)
    - Source — relative paths from the doc file to each source file it covers

11. **Update the project Overview:** Add rows to the module table for each new doc. For excluded modules (from cgexclude.md), add a row with the description from cgexclude and *excluded* in the Doc column. Never add "not yet documented" placeholder rows — a module either has docs, is excluded, or is not listed.

12. **Update IDE visibility (language-specific):** For .NET projects with a `.csproj`, ensure `<None Include="_codeguide\**\*.md" />` is in an ItemGroup. Skip for other languages.

13. **Report:** List what was created and what was skipped (already documented or excluded).

## Parallelism

For large scopes, use parallel subagents — one per project. Each subagent receives the Documentation Guide, local rules, and its project's scope, then creates docs independently. Subagents can further parallelize per module if the project has many undocumented files.

Include the relevant `_codeguide/Overview.md` in every subagent prompt.

## Rules

- Follow the Documentation Guide exactly — read it first, not from memory.
- Apply local rules from `local-rules.md` on top of the guide.
- Do not include API signatures, line-by-line walkthroughs, or internal algorithm details.
- Do not include code-derived values: formulas, thresholds, constants, or expressions copied from source.
- Do not reference projects the code doesn't depend on.
- Do not modify existing docs. That is `/codeguide-maintain`'s job.
- Capability summaries are the highest-value section — a reader should know if the module is relevant without reading source.
- Write docs as if they were written first and the code was written to satisfy them.
