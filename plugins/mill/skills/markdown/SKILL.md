---
name: markdown
description: Markdown formatting rules for generated files. Use when writing .md files.
---

# Markdown Formatting Skill

Rules for metadata formatting in generated markdown files. Language-agnostic.

Full format reference: `plugins/mill/doc/formats/markdown.md`

---

## Fenced YAML for metadata

Use fenced YAML code blocks (` ```yaml `) for all metadata in generated `.md` files. This includes status files, review reports, child registry entries, and any other machine-written markdown.

YAML frontmatter (`---`) is reserved for system-parsed metadata in skill definitions (`SKILL.md`) and plugin manifests. Never use frontmatter for human-facing metadata in generated files — previewers hide it.

## Structure

- Use markdown headings (`#`, `##`) to structure the document.
- Place metadata in fenced YAML code blocks immediately after their heading.
- Group related fields in a single block. Use separate blocks for separate concerns (e.g., task metadata vs. timeline).
