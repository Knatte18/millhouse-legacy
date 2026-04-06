# kanban.md Format Reference

Reference for the [kanban.md VS Code extension](https://marketplace.visualstudio.com/items?itemName=wguilherme.kanban-md) file format. Mill reads and writes kanban board files directly.

Source: [wguilherme/kanban.md](https://github.com/wguilherme/kanban.md) — verified against `src/markdownParser.ts` (2026-04-03).

## Board Files

Mill uses two separate board files in `_millhouse/`:

| File                             | Git       | Purpose                        | Columns                                                       |
|----------------------------------|-----------|--------------------------------|---------------------------------------------------------------|
| `_millhouse/backlog.kanban.md`   | Tracked   | Manual task entry, user-managed | Backlog, Spawn, Delete                                        |
| `_millhouse/scratch/board.kanban.md`     | Gitignored | Active work, Mill-managed      | Discussing, Planned, Implementing, Testing, Reviewing, Blocked |

### Backlog board (`_millhouse/backlog.kanban.md`)

The user's task inbox. Git-tracked so it syncs between PCs. The user adds tasks manually (via the kanban extension or `mill-add`), drags them to Spawn when ready, and `mill-start` or `mill-spawn` claims them. `mill-inbox` imports GitHub issues here.

```markdown
# Project Name

## Backlog

### Task Title

    ```md
    Description text here.
    ```

## Spawn

## Delete
```

Columns:
- **Backlog** — tasks that exist but aren't ready to start
- **Spawn** — tasks ready to be claimed. `mill-start` (in-place) or `mill-spawn` (worktree) takes the first task from here.
- **Delete** — tasks the user wants removed. `mill-cleanup` empties this column.

### Work board (`_millhouse/scratch/board.kanban.md`)

Active work state. Gitignored — local runtime state only. Each worktree gets its own independent copy. `mill-spawn` creates the file in new worktrees with the task pre-populated in `## Discussing`. No shared state between worktrees, no symlinks, no lockfile.

```markdown
# Project Name

## Discussing

### Task Title

    ```md
    Description text here.
    ```

## Planned

## Implementing

## Testing

## Reviewing

## Blocked
```

Columns (each column IS the phase — no `[phase]` suffix needed):
- **Discussing** — `mill-start` is discussing the task with the user
- **Planned** — discussion complete, ready for `mill-go` (which writes the plan autonomously)
- **Implementing** — `mill-go` is writing code
- **Testing** — tests running
- **Reviewing** — code review in progress
- **Blocked** — waiting on user input or upstream fix

## Task Title Format

Task titles use `### Title` format. No `[phase]` suffix in the work board — the column determines the phase.

In the backlog board, tasks may optionally use `[backlog]` phase or no phase at all:

```markdown
### Fix input validation [backlog]
### Simple task
```

Task identity is the title text *without* any `[phase]` suffix. `### Fix input validation [backlog]` → title = `Fix input validation`.

Slug for branch names: derived from title (without phase), lowercase, spaces to hyphens, remove special characters. "Fix input validation" → `fix-input-validation`.

## Task Header Format

The extension supports two task formats, configurable in VS Code settings:

- **Header format** (default): `### Task Title`
- **List format**: `- Task Title`

Mill always uses header format (`### `). Both are detected by the parser via `isTaskTitle()`.

**Important:** In list format, a non-indented `- ` line that isn't a recognized property is treated as a new task title. This is why unknown metadata fields are dangerous — see "Unknown fields" below.

## Metadata Fields

Only use fields recognized by the extension parser. The parser matches this exact regex:

```
/^\s*- (due|tags|priority|workload|steps|defaultExpanded):\s*(.*)$/
```

### Supported fields

| Field | Syntax | Values | Description |
|-------|--------|--------|-------------|
| `tags` | `- tags: [tag1, tag2]` | Comma-separated in brackets | Labels shown on card |
| `priority` | `- priority: high` | `low`, `medium`, `high` | Colored left border (green/yellow/red) |
| `workload` | `- workload: Hard` | `Easy`, `Normal`, `Hard`, `Extreme` | Case-sensitive. Effort indicator |
| `due` | `- due: 2026-04-15` | `YYYY-MM-DD` | Deadline |
| `defaultExpanded` | `- defaultExpanded: true` | `true`, `false` | Whether card starts expanded |
| `steps` | `- steps:` | (triggers subtask mode) | Followed by indented checkboxes |

### Inline hashtags

Lines starting with `#` (not `##` or `###`) are parsed as tags via the regex `/#[\w\-@$%✓0-9]+/g`. These appear immediately after the task title:

```markdown
### Design Login Page
#design #ui #frontend
- priority: high
```

### Steps (subtasks)

The `- steps:` field enables checkbox parsing. Subtasks must be indented 2+ spaces:

```markdown
### Implement Auth
- steps:
  - [ ] Setup JWT tokens
  - [x] Add OAuth providers
  - [ ] Write security tests
```

### Unknown fields

**Do NOT use unrecognized field names** (e.g. `- created:`, `- phase:`, `- assignee:`). The parser behavior is:

1. The unknown line does not match any property regex.
2. The parser finalizes the current task (saves it without the unknown field).
3. The line is re-processed from the top of the parse loop.
4. If the line starts with non-indented `- ` → it becomes a **new task card** with the field text as its title (e.g. a task titled "created: 2024-01-01").
5. If the line is indented → it is silently ignored.

This is worse than just losing metadata — it corrupts the board structure.

## Descriptions

**Descriptions must use indented ` ```md ` code blocks.** Plain text after metadata is NOT parsed as a description — the parser ignores or misinterprets it.

### Correct format

```markdown
### Add OAuth Support
- priority: high
- tags: [auth, backend]

    ```md
    Google OAuth first. Must support token refresh.
    Multi-line descriptions work.
    ```
```

The generator uses 4-space indentation for the code block. The parser accepts 1+ spaces (`/^\s+```md/`).

### Why not plain text?

A plain text line after metadata (or an empty line) does not match any property regex. The parser finalizes the task, then re-processes the line. The line either:
- Becomes an accidental new task (if it starts with `- `)
- Is silently discarded (any other content)

**Drag-and-drop destroys plain text descriptions.** The extension regenerates the entire file via `generateMarkdown()`, which only outputs descriptions it successfully parsed (i.e. from ` ```md ` blocks).

## Drag-and-Drop Behavior

When a card is dragged between columns in the VS Code panel:

1. The in-memory board model is updated (`moveTask()` splices the task between column arrays).
2. `generateMarkdown()` regenerates the **entire file** from the board model.
3. The new markdown is written to disk.

### What this means

- Any content the parser didn't capture is **permanently lost** (plain text descriptions, unknown fields, comments between tasks).
- The file is normalized to the generator's format:
  - Blank line after board title, after each column heading, and after each task block.
  - Properties written without indentation, in order: tags → priority → workload → due → defaultExpanded → steps.
  - Descriptions wrapped in `    ```md` blocks.
- Task order within a column may change (the dragged card lands at the drop position).

### Blank line requirements

The parser skips empty lines unconditionally (`continue`). Blank lines are not required between headings and metadata — but the generator always adds them, so after any drag-and-drop the file will have blank lines everywhere.

## Task Format

### Minimal task (what mill-add creates)

```markdown
### Add OAuth Support
```

### Full task

```markdown
### Add OAuth Support
- priority: high
- tags: [auth, backend]
- due: 2026-04-15

    ```md
    Google OAuth first. Must support token refresh.
    ```
```

### Task with steps

```markdown
### Implement Auth
- priority: high
- steps:
  - [x] Setup JWT tokens
  - [ ] Add OAuth providers
  - [ ] Write security tests
```

## How Mill Uses the Boards

| Operation | Board | What Mill does |
|-----------|-------|---------------|
| **Create task** (mill-add) | backlog | Add `### Title` under `## Backlog` in `_millhouse/backlog.kanban.md` |
| **Import issues** (mill-inbox) | backlog | Add new issues under `## Backlog` in `_millhouse/backlog.kanban.md` |
| **Claim task** (mill-start/mill-spawn) | both | Remove from `## Spawn` in backlog, add to `## Discussing` in work board |
| **Phase transition** (mill-go) | work | Move task between columns in `_millhouse/scratch/board.kanban.md` |
| **Complete task** (mill-go/mill-merge) | work | Remove task from `_millhouse/scratch/board.kanban.md` entirely |
| **Abandon task** (mill-abandon) | both | Remove from work board, add back to `## Backlog` in backlog |
| **Clean up** (mill-cleanup) | backlog | Remove all tasks from `## Delete` in backlog |
| **Dashboard** (mill-status) | both | Read both boards, display combined counts |

## Task Block Boundaries

A task block starts at `### Title` (with or without `[phase]`) and ends immediately before the next `###`, `##`, or end of file. When moving or reading tasks, capture the entire block.

## Column Section Boundaries

A column section starts at `## Column Name` and ends immediately before the next `##` or end of file. When inserting a task into a column, append it at the end of the column section (before the next `##`).

## Write Rules

- **Backlog board** (`_millhouse/backlog.kanban.md`):
  - Git-tracked. Writes must be committed and pushed (skills that modify backlog handle this).
  - Single source of truth across all worktrees (via git).
  - Columns: Backlog, Spawn, Delete.

- **Work board** (`_millhouse/scratch/board.kanban.md`):
  - Gitignored, local-only per worktree.
  - **Parent worktree / main repo:** work board for in-place tasks (created by `mill-setup` or `mill-start`).
  - **Task worktree** (spawned by `mill-spawn`): board created by `mill-spawn.ps1` with the spawned task under `## Discussing`, other columns empty.
  - **Fresh clone:** no work board exists. Run `mill-setup` to create it, or `mill-start` creates it on first task claim.
  - Columns: Discussing, Planned, Implementing, Testing, Reviewing, Blocked.

- Each worktree updates its own `_millhouse/scratch/board.kanban.md`. No shared state between worktrees.
- Only use extension-supported metadata fields (tags, priority, workload, due, defaultExpanded, steps).
- Descriptions use indented ` ```md ` code blocks — never plain text.
