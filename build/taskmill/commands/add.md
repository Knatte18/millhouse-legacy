---
description: "Add a checkbox item to a file"
argument-hint: "<file> <Title: description>"
---

Add an item to a file with `- [ ] **Title**` format.

## Steps

1. Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_add.py <file-path> "<Title: description>"`.
   - If the input contains a colon, the part before becomes the bold title and the part after becomes an indented description.
   - If no colon, the entire input becomes the bold title with no description.
2. Works on `doc/backlog.md` and `.llm/plans/*.md`.
3. Appends the formatted entry followed by a blank line.
