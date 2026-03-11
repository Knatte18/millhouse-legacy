---
description: "Generate a work-journal entry from recent commits"
argument-hint: "<cutoff> [language-prefix] [guidance]"
---

Generate a work-journal entry from recent git commits. Prints to stdout only — does not modify any files.

- **Cutoff (required):** ISO 8601 timestamp or natural-language date (e.g. `today`, `yesterday`, `2h ago`, `2026-03-01`). No default — the user must specify when to start from.
- **Language prefix (optional):** any recognizable prefix of a language name. Examples: `nor`, `no`, `norwegian`, `eng`, `en`, `english`, `fr`, `french`. Default: English.
- **Guidance (optional):** free-text for emphasis, length, or focus. Examples: `"Emphasize the refactoring work"`, `"3 sentences"`, `brief`, `detailed`.
- Arguments can appear in any order. Quoted strings are treated as guidance.
- Runs `git log --oneline --since=<cutoff>` to gather commits since the cutoff. When the cutoff is a bare date (e.g. `today` → `2026-03-08`), append ` 00:00:00` so git includes commits on that date.
- Generates plain narrative prose — dense, technical, work-journal style. No headings, no bullet points, no markdown formatting.
- Default length: 3-4 sentences. User can override with guidance like `detailed`, `brief`, or `5 sentences`.
- Start directly with the substance. No preamble like "Today's work...", "This session...", "The main focus was...".
- Write for a non-technical audience (CEO, stakeholders). Describe work in domain terms. No file paths, no variable/parameter names, no class names, no code references.
- Prints the entry to stdout. Does NOT read or write any files.
- Does NOT read `doc/changelog.md`.
