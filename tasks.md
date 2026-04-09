# Tasks

## mill-merge worktree detection is too weak
- mill-merge checks if you're in a linked worktree (not the first entry in `git worktree list`), but this doesn't verify it's a mill-managed worktree.
- A manually created worktree (via `git worktree add` or VS Code extension) passes the check even though mill-merge shouldn't run there.
- Fix: check that `_millhouse/scratch/status.md` exists and has `task:` and `phase:` fields — that's what mill-spawn writes. Without those, refuse to merge.
- Same fix applies to mill-abandon.
