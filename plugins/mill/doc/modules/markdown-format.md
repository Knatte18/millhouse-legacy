# Markdown Format for Generated Files

Rules for metadata in markdown files that Mill skills generate (status files, review reports, child registry entries, etc.).

## When to Use What

| Format | Use case |
|--------|----------|
| YAML frontmatter (`---`) | Skill and plugin metadata parsed by the system (e.g., `SKILL.md`, `plugin.json`). Never for human-facing metadata. |
| Fenced YAML code block | Human-readable metadata in generated files. Renders visibly in all markdown previewers. |

## Fenced YAML Format

Wrap metadata in a fenced code block with the `yaml` language tag:

````markdown
# Document Title

```yaml
task: Fix login validation
phase: implementing
parent: main
```

## Timeline
```text
discussing              2026-04-08T10:23:15Z
implementing            2026-04-08T11:10:00Z
```
````

## Incorrect Formats

**Bare YAML (no fence):** Invisible in most markdown previewers.

````markdown
# Document Title

task: Fix login validation
phase: implementing
````

**YAML frontmatter for generated files:** Hidden by previewers like "Markdown Preview Enhanced."

````markdown
---
task: Fix login validation
phase: implementing
---
````

## Rules

1. All metadata sections in generated `.md` files use fenced YAML code blocks.
2. YAML frontmatter is reserved for system-parsed metadata in skill definitions (`SKILL.md`) and plugin manifests.
3. Each fenced block should group related fields (e.g., task metadata in one block, timeline in another).
4. Headings (`#`, `##`) structure the document. Metadata blocks follow their heading.
