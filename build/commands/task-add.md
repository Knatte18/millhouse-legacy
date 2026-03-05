---
description: "Add a checkbox item to a file"
argument-hint: "<file-path> <Title: description>"
---

## Behavior

Add an item to a file with `- [ ] **Title**` format.

Run: `python ~/.claude/scripts/task_add.py <file-path> <Title: description>`

- If the input contains a colon, the part before becomes the bold title and the part after becomes an indented description.
- If no colon, the entire input becomes the bold title with no description.
- Works on both `doc/backlog.md` and `.llm/plans/YYYY-MM-DD-HHMMSS-<slug>.md`.
- Appends the formatted entry followed by a blank line.
