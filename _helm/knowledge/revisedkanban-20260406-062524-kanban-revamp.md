# Task: Forbedre kanban-oppsettet

## Patterns established
- Two-board model: `backlog.kanban.md` (git-tracked, 3 columns) + `board.kanban.md` (gitignored, 6 columns per worktree)
- All skills writing to backlog must commit and push (helm-add, helm-sync, helm-spawn, helm-start, helm-abandon, helm-cleanup)
- Work board uses columns as phases — no `[phase]` suffix in task headings
- Separate fixer agent for review findings (both plan review and code review) produces better results than self-fixing

## Existing patterns discovered
- `feedback-inbox` skill in `plugins/conduct/` also references kanban boards — easy to miss since it's outside the helm plugin
- `testing-guide.md` has hardcoded board references in verification checklists — must be updated alongside skill changes
- `helm-spawn.ps1` stdout contract: `Write-Output` is the only allowed stdout emission; `Write-Host` goes to console stream and doesn't interfere

## Gotchas
- Windows NTFS junctions don't work with git worktrees (git doesn't follow them, can cause data loss on deletion)
- File symlinks on Windows require Developer Mode — not available on many corporate machines
- `core.symlinks=false` is the Windows default — git stores symlinks as text files
- Cross-worktree backlog writes need `git -C <parent-path>` and a pre-commit conflict check (`git status --porcelain`)
- helm-abandon must capture task block from child's board BEFORE worktree deletion — status.md only has the title, not the body
