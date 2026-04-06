# Handoff Brief Format

The handoff brief is written by `mill-spawn.ps1` into the **parent** worktree at `_millhouse/handoff.md` (git-tracked). The new worktree inherits it via git. It provides background context for the receiving `mill-start` session.

Canonical source: `plugins/mill/scripts/mill-spawn.ps1` (the script generates the file directly).

## Consumer

`mill-start` reads the handoff brief from `_millhouse/handoff.md` during Phase: Select (path 0). The brief's `## Issue` identifies the task, and `## Discussion Summary` provides prior context. The brief informs but does not constrain — `mill-start` runs its own Explore and Discuss phases.

## File Location

`_millhouse/handoff.md` (git-tracked).

The file is overwritten on each spawn and deleted by `mill-start` after consumption (committed as `spawn-consume: <task>`). Each spawn commit (`spawn: <task>`) includes both `_millhouse/backlog.kanban.md` and `_millhouse/handoff.md`.

## Format

```markdown
# Handoff: <task title>

## Issue
<task title>

## Parent
Branch: <parent branch name>
Worktree: <parent project path (cwd)>

## Discussion Summary
<task description or title — multi-line descriptions are 4-space indented>

## Config
- Verify: <verify command or "N/A">
- Dev server: <dev server command or "N/A">
```

## Section Details

### `## Issue`

Contains only the task title (`$TaskTitle`). No `#<number>:` prefix — the script does not extract a GitHub issue number.

### `## Parent`

The parent branch name and project path (cwd at spawn time, which may be a subdirectory of the worktree root). Used by `mill-start` to resolve the parent for merge operations.

### `## Discussion Summary`

The task description from the backlog (if present), otherwise the task title. Multi-line descriptions have each line indented with 4 spaces (matching kanban.md code block indentation).

### `## Config`

Verify and dev-server commands extracted from `_millhouse/config.yaml`. Defaults to `"N/A"` if not configured.
