## Separate kanban boards
**Why:** The VS Code kanban.md extension shows each `.kanban.md` file as a separate visual board. Having one board per column gives a cleaner UI with focused views (backlog only, in-progress only, etc.)
**Trade-off:** "Move task" is now a cross-file operation (cut from one file, paste into another) instead of an in-file edit. Slightly more complex for skills, but the mapping from column to file is 1:1 and deterministic.
**Alternatives rejected:** Single file with all columns (original design — visually cluttered), directory of per-task files (too granular, extension doesn't support it well)
