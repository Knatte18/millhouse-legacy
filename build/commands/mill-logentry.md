---
description: "Generate a changelog entry from recent git commits and print to stdout"
argument-hint: "[since] [language] [length/emphasis]"
---

## Behavior

Generate a changelog entry from recent git commits. Prints to stdout only — does not write to `doc/changelog.md`.

- Accepts optional arguments in any order or combination:
  - **cutoff time**: ISO 8601 timestamp or natural-language date (e.g. `yesterday`, `2026-03-01`). If omitted, reads `doc/changelog.md` and finds the date of the newest `## YYYY-MM-DD` heading, then uses that date as the cutoff.
  - **language**: e.g. `norwegian`, `french`. Default: English.
  - **length/emphasis guidance**: e.g. `brief`, `detailed`, `focus on architecture decisions`.
- Runs `git log --oneline --since=<cutoff>` to gather commits since the cutoff.
- Reads `doc/changelog.md` to match the existing tone and format.
- Generates a single entry as dense, technical narrative prose — work-journal style covering what was done, key decisions, discoveries, and open items.
- Prints the entry to stdout (with the `## YYYY-MM-DD` heading using today's date). Does NOT modify any files.
- Honors the language argument if provided; otherwise defaults to English.
