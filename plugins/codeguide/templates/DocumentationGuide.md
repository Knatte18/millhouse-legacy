# Documentation Guide

This document defines how code documentation is written and organized. It is owned by the codeguide plugin — do not edit locally. Repo-specific additions go in `_codeguide/local-rules.md`.

## Purpose

Documentation should fully define what a module does, how it is used, and its expected behavior — without requiring the reader to look at source code. A developer (or AI assistant) reading only the documentation should be able to:

1. Understand what the module does and why it exists
2. Know when and where it is used
3. Decide whether this module's code is relevant to a given task

Internal implementation details (algorithms, data structures, control flow) belong in the code, not the docs.

Think of it this way: **the doc should read as if it was written first, and the code was then written to satisfy it.**


## Where Documentation Lives

Each project has its own `_codeguide/` folder, colocated with the code. The underscore prefix ensures the folder sorts before code folders in file explorers.

```
my-project/
├── _codeguide/
│   ├── Overview.md          ← entry point (always at _codeguide/ root)
│   └── modules/
│       ├── ModuleA.md
│       ├── ModuleB.md
│       └── ...
└── src/
    └── ...
```

`Overview.md` is always at the root of `_codeguide/` — it is the entry point. All module docs go in `_codeguide/modules/`. This separation makes the entry point immediately visible.

Repo-level docs (like this file) live in `_codeguide/` at the repo root.


## Naming and Granularity

### One doc per component

Each source file or source folder gets its own doc file. The doc file name must exactly match the source name — this is the contract the reverse lookup depends on. Never mangle, abbreviate, or prefix a doc name to avoid a collision; use sub-area folders instead (see below).

- `parser.py` → `_codeguide/modules/Parser.md`
- `utils/` (folder) → `_codeguide/modules/Utils.md`
- `inventory/` (folder with multiple files) → `_codeguide/modules/Inventory.md`

When several small, related source files in a folder share a single doc named after the folder (e.g., `Exporters.md` covers `CsvExporter.cs`, `JsonExporter.cs`, etc.), the reverse lookup uses these steps:

1. Given `Foo.cs`, look for `modules/Foo.md`.
2. If not found, use the parent folder name: `Foo.cs` is in `Bar/` → look for `modules/Bar.md`.
3. If not found at the top level, check sub-area folders: look for `modules/*/Foo.md` or `modules/*/Bar.md`.

No searching required at any step — the Overview's module table resolves which sub-area a name lives in. Never fall back to Grep or Glob to find a doc — if the Overview doesn't list it, the file is undocumented.

Even small components (a 20-line interface, a single struct) get their own doc. A short doc is better than one buried inside a larger file.

### When one doc isn't enough

If a component is large enough that a single doc would be too long, create a subfolder:

```
_codeguide/
├── modules/
│   ├── QueryEngine/
│   │   ├── Overview.md
│   │   └── IndexStrategy.md
```

### Sub-area folders

Sub-area folders serve two purposes: organization and disambiguation. They are **mandatory** when two source folders share a name under different parents (e.g., `core/fetch/` and `orchestration/fetch/`). Without sub-areas, both would map to `modules/Fetch.md`, breaking the reverse lookup. The doc tree must mirror the source tree's nesting to keep each name's lookup path unique.

Sub-area folders are also useful when the flat `modules/` folder becomes hard to scan, even without name collisions.

Each sub-area gets its own `Overview.md` that serves as a routing table for that area:

```
_codeguide/
├── Overview.md              ← project entry point
└── modules/
    ├── Converters.md          ← flat module (no sub-area)
    ├── Scheduling/
    │   ├── Overview.md        ← sub-area routing table
    │   ├── TaskQueue.md
    │   └── RetryPolicy.md
    └── Storage/
        ├── Overview.md
        └── BlobStore.md
```

The project-level Overview's module table lists sub-areas by name and links to their Overview. The sub-area Overview then lists its own modules. This creates a two-level routing hierarchy: project Overview → sub-area Overview → module doc.

**Cross-subfolder links:** A sub-area Overview or module doc may link to a *different* sub-area's `Overview.md` — never to a specific doc within it. Links between sub-area Overviews are allowed because Overviews are stable routing tables. For flat modules in the parent `modules/` folder, refer to them by plain-text name (the project Overview resolves names to files).

### Minimal projects

Some projects (test harnesses, standalone tools) have no meaningful module decomposition. These projects get an `Overview.md` with no `modules/` folder. The Overview states what the project is, what it does not own, and includes whatever project-specific content is useful (e.g., a coverage matrix for a test project). Do not create empty `modules/` folders or stub module docs.

### Test folders

Test folders may get an `Overview.md` describing test coverage scope, organization, and which source modules they exercise. Individual test files do not get their own module docs — they are not modules to route to. If a test folder needs to be excluded from doc generation entirely, add it to `cgignore.md`.

### Project overview

Each project gets an `Overview.md` as the entry point, describing the project's role, its main modules, and how they relate.


## What Goes in Each Doc

### Project Overview (`Overview.md`)

The Overview is the first file read when entering a project. It must let the reader decide "is this project relevant to my task?" without opening any other file. Structure it for fast scanning:

- **What this project is responsible for** — sharp boundary in prose
- **What this project does NOT own** — explicit negative boundaries. "This project does not handle X — that lives in [other project]." The negative space is what lets a reader confidently skip the project.
- **Dependencies with direction** — "consumes X" (what it uses) and "consumed by Y" (what uses it). Explicit direction helps trace data flows.
- **Module table with routing hints** — each module gets a one-line description and a "touch this when..." hint so the reader can identify the right module without opening every doc:

```
| Module | Description | Touch this when... |
|---|---|---|
| WidgetParser | Parses widget definition files | ...changing how widget configs are loaded or validated |
| MetricsBucket | Aggregates raw metric samples | ...modifying how counters or histograms are collected |
```

- Any cross-cutting patterns or conventions specific to this project

### Repo Overview

The repo-level `_codeguide/Overview.md` is the top-level entry point. It routes readers to the right project. Structure:

- **Project Map table** — one row per project with columns: Project, Doc (link to project Overview), Owns (one-line scope), Touch this when... (routing hint). Projects without `_codeguide/` get a row with an italicized note instead of a link (e.g., *not documented — leaf project, no downstream consumers*).
- **Dependency graph** — ASCII tree showing project relationships with direction. Helps readers understand the layering.
- **Documentation system pointer** — link to this guide.

The repo Overview does not describe individual modules — that is each project Overview's job.

### Module Doc

A module doc answers these questions:

1. **What** — what does this module represent or do?
2. **Why** — why does it exist? What problem does it solve?
3. **Usage** — how is it used by other code? What are the key interfaces and their contracts?
4. **Behavior** — what are the expected behaviors, invariants, or guarantees?
5. **When not to use** — common misuses or wrong turns. What looks like it belongs here but doesn't? Where should consumers go instead? This negative-space guidance prevents wasted time.
6. **Relationships** — what does it depend on, and what depends on it? Use plain-text area or concept names (e.g., "the Pipeline stages", "the Schema data model"), not markdown links to sibling files. The parent Overview resolves names to files. For cross-project dependencies, link to the other project's Overview. Omit this section entirely if the module only depends on siblings within the same project.
7. **Source** — relative paths from the doc file to the source file(s) it documents. This lets tools and AI assistants locate source without searching. Each entry is a markdown link with a brief role note when the doc covers multiple files:

```markdown
## Source

- [BlobCache.cs](../../Storage/BlobCache.cs)
```

For multi-file docs, annotate each entry so the reader knows which file covers what:

```markdown
## Source

- [CsvExporter.cs](../../Exporters/CsvExporter.cs) — CSV format
- [JsonExporter.cs](../../Exporters/JsonExporter.cs) — JSON format
```

Paths are relative to the markdown file, not the repo root. This works regardless of which directory the session runs from. The `/codeguide-generate` skill writes these paths when creating docs, and `/codeguide-maintain` validates that they still resolve.

Do **not** include:
- Line-by-line code walkthroughs
- Internal algorithm descriptions (that's what code comments are for)
- Copy-pasted API signatures (they'll drift from the code)
- Code-derived values: formulas, thresholds, constants, or expressions copied from source. If a value belongs in the code, it belongs only there. A doc that copies it creates a second source of truth that will drift and mislead.
- References to projects that the code does not depend on. If a module is an extension point, say so and point readers to the consuming project's own docs. The consuming project is responsible for documenting what it plugs in.
- **Links to sibling docs** (other docs in the same folder or subfolder). Only the parent Overview links to its children. This means editing a module doc never forces updates to its siblings — only the parent Overview may need a row update. Referring to siblings by name in plain text is fine (e.g., "see ClassTypes for class-level patterns") — the parent Overview resolves names to files. If a module doc needs to reference a different area entirely (e.g., a different subfolder), link to that area's Overview.md — never to a specific doc within it. Overviews are stable routing tables that rarely change, so those links don't create update cascades.

Do include:
- Conceptual descriptions of the public interface
- **Capability summaries** — describe what the module can do in plain language, without listing method signatures. A reader should be able to tell from the doc alone whether this module is relevant to a given task. For example: "Buckets can test whether a timestamp falls within their window, compute the percentile of a sample within the bucket, and expose the min/max range across the bucket."
- Usage examples where they clarify behavior — conceptual only. Do not embed method calls, formulas, or values from source. Examples must not depend on code remaining unchanged.
- Edge cases or non-obvious behavior

### Utility / Helper Modules

For modules with many small stateless functions (e.g., math utilities), don't list signatures — they'll drift. Instead describe:

- What categories of problems the module solves
- When a consumer would reach for each category (and when they shouldn't)
- Assumptions and invariants (default tolerances, unit conventions, input ordering)
- Which higher-level modules depend on each category


## What does NOT belong in `_codeguide/`

`_codeguide/` is for stable module documentation only. Working analyses, gap assessments, planning artifacts, and scratch notes belong elsewhere (e.g., `.llm/` if using taskmill). If a document describes what *should* change rather than what *currently exists*, it is not a doc.


## Maintenance

- Update docs when module behavior changes — not for every code edit
- A doc that's wrong is worse than no doc. If a doc drifts, fix or delete it
- Docs are tracked in version control alongside the code they describe
- If you encounter a broken cross-reference, fix it on the spot. If the rename was part of the current task, fix all references within the same session. Don't hunt for broken refs outside the current task scope
- The "Touch this when..." column in module tables only needs to cover non-obvious cases. If the module name and description already make relevance clear, the hint can be omitted or left blank
