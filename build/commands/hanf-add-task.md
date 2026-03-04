---
description: "Add a checkbox item to a file"
argument-hint: "<file-path> <Title: description>"
---

Read and follow ~/.claude/skills/formats.md

## Behavior

Add an item to a file with `- [ ] **Title**` format.

1. Take file path and `Title: description` as parameters.
2. Use `python ~/.claude/scripts/hanf_task_add.py <file-path> "<Title: description>"` to append the entry.
3. If the input contains a colon, the part before becomes the bold title and the part after becomes an indented description.
4. If no colon, the entire input becomes the bold title with no description.
5. Works on both `doc/backlog.md` and `.llm/plans/YYYY-MM-DD-HHMM-<slug>.md`.
