---
description: "Generate a changelog entry from recent git commits"
argument-hint: "[since] [language] [length/emphasis]"
---

Generate a changelog entry from recent git commits. Prints to stdout only — does not write to `doc/changelog.md`.

## Steps

1. Parse optional arguments (in any order or combination):
   - **cutoff time**: ISO 8601 timestamp or natural-language date (e.g. `yesterday`, `2026-03-01`). If omitted, read `doc/changelog.md` and find the date of the newest `## YYYY-MM-DD` heading, then use that date as the cutoff.
   - **language**: e.g. `norwegian`, `french`. Default: English.
   - **length/emphasis guidance**: e.g. `brief`, `detailed`, `focus on architecture decisions`.
2. Run `git log --oneline --since=<cutoff>` to gather commits since the cutoff.
3. Read `doc/changelog.md` to match the existing tone and format.
4. Generate a single entry as dense, technical narrative prose — work-journal style covering what was done, key decisions, discoveries, and open items.
5. Print the entry to stdout (with the `## YYYY-MM-DD` heading using today's date). Do NOT modify any files.
6. Honor the language argument if provided; otherwise default to English.
