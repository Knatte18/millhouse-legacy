# Task: Omskriv kanban til separate kanbans

## Patterns established
- Kanban boards live in `kanbans/` directory with 4 separate `.kanban.md` files (one per column)
- "Move task" = cross-file operation: cut from source file, paste into target file
- Each board file has one `#` title (project name) and one `##` column heading
- Worktrees get all 4 files (others empty) so new tasks can be created in any column

## Gotchas
- The VS Code kanban.md extension requires `.kanban.md` file extension — filenames like `backlog.kanban.md` work
- `feedback-inbox` skill in `plugins/conduct/` also references kanban boards — easy to miss since it's outside the helm plugin
- `testing-guide.md` in helm docs has hardcoded `.kanban.md` paths in verification checklists — must be updated alongside skill changes
- When migrating in a worktree, the `.kanban.md` only has the worktree's task — the full board is on the parent branch
