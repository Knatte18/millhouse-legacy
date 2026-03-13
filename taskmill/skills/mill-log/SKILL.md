---
name: mill-log
description: "Generate a work-journal entry from recent commits"
argument-hint: "<cutoff> [language-prefix] [guidance]"
---

Generate a work-journal entry from recent git commits. Prints to stdout only — does not modify any files.

## Steps

1. Parse arguments (any order):
   - **Cutoff (required):** ISO 8601 timestamp or natural-language date (e.g. `today`, `yesterday`, `2h ago`, `2026-03-01`). No default — the user must specify when to start from.
   - **Language prefix (optional):** any recognizable prefix of a language name. Examples: `nor`, `no`, `norwegian`, `eng`, `en`, `english`, `fr`, `french`. Default: English.
   - **Guidance (optional):** free-text for emphasis, length, or focus. Examples: `"Emphasize the refactoring work"`, `"3 sentences"`, `brief`, `detailed`. Quoted strings are treated as guidance.
2. Run `git log --oneline --since=<cutoff>` to gather commits since the cutoff. When the cutoff is a bare date (e.g. `today` → `2026-03-08`), append ` 00:00:00` so git includes commits on that date.
3. Generate plain narrative prose — dense, technical, work-journal style. No headings, no bullet points, no markdown formatting.
4. Default length: 3-4 sentences. User can override with guidance like `detailed`, `brief`, or `5 sentences`.
5. Start directly with the substance. No preamble like "Today's work...", "This session...", "The main focus was...".
6. Write for a non-technical audience (CEO, stakeholders). Describe work in domain terms. No file paths, no variable/parameter names, no class names, no code references.
7. Print the entry to stdout. Do NOT read or write any files.
8. Do NOT read `doc/changelog.md`.
