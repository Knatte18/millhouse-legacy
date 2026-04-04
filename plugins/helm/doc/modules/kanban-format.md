# kanban.md Format Reference

Reference for the [kanban.md VS Code extension](https://marketplace.visualstudio.com/items?itemName=wguilherme.kanban-md) file format. Helm reads and writes kanban board files directly.

Source: [wguilherme/kanban.md](https://github.com/wguilherme/kanban.md) — verified against `src/markdownParser.ts` (2026-04-03).

## File Location

Single board file at the repo root:

```
kanbans/board.kanban.md
```

The file contains one `#` project title and five `##` column headings. The `.kanban.md` extension triggers detection by the VS Code extension.

## Structure

The board file follows this structure:

```markdown
# Project Name

## Backlog

### Task Title [phase]
- priority: high
- tags: [tag1, tag2]

    ```md
    Description text here.
    ```

## Spawn

## In Progress

## Done

## Blocked
```

- `#` — project title (one per file, must be line 1)
- `##` — column headings (five columns in order: Backlog, Spawn, In Progress, Done, Blocked)
- `###` — tasks within a column, optionally with `[phase]` suffix

## Columns Helm Uses

| Column | Heading | Meaning |
|--------|---------|---------|
| **Backlog** | `## Backlog` | Task exists, not started |
| **Spawn** | `## Spawn` | Ready to be spawned into a worktree |
| **In Progress** | `## In Progress` | Active work (discussing, implementing, reviewing) |
| **Done** | `## Done` | Completed |
| **Blocked** | `## Blocked` | Needs user input or upstream fix |

Columns can have an `[Archived]` suffix (e.g. `## Done [Archived]`) to collapse them in the VS Code panel.

## Task Title and Phase

Task titles use the format `### Title [phase]` where `[phase]` is optional:

```markdown
### Fix input validation [implementing]
### Add retry logic [backlog]
### Simple task
```

Valid phase values: `backlog`, `discussing`, `planned`, `implementing`, `testing`, `reviewing`, `blocked`, `complete`.

To update phase: edit the `[phase]` in the `###` heading directly. To remove phase: remove the `[...]` suffix.

Task identity is the title text *without* the `[phase]` suffix. `### Fix input validation [implementing]` → title = `Fix input validation`, phase = `implementing`.

Slug for branch names: derived from title (without phase), lowercase, spaces to hyphens, remove special characters. "Fix input validation" → `fix-input-validation`.

## Task Header Format

The extension supports two task formats, configurable in VS Code settings:

- **Header format** (default): `### Task Title`
- **List format**: `- Task Title`

Helm always uses header format (`### `). Both are detected by the parser via `isTaskTitle()`.

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

This is worse than just losing metadata — it corrupts the board structure. Phase is tracked in the `###` heading, not as a metadata field.

## Descriptions

**Descriptions must use indented ` ```md ` code blocks.** Plain text after metadata is NOT parsed as a description — the parser ignores or misinterprets it.

### Correct format

```markdown
### Add OAuth Support [implementing]
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

### Minimal task (what helm-add creates)

```markdown
### Add OAuth Support [backlog]
```

### Full task

```markdown
### Add OAuth Support [implementing]
- priority: high
- tags: [auth, backend]
- due: 2026-04-15

    ```md
    Google OAuth first. Must support token refresh.
    ```
```

### Task with steps

```markdown
### Implement Auth [implementing]
- priority: high
- steps:
  - [x] Setup JWT tokens
  - [ ] Add OAuth providers
  - [ ] Write security tests
```

## How Helm Uses the Board

| Operation | What Helm does |
|-----------|---------------|
| **Create task** (helm-add) | Add `### Title [backlog]` under the `## Backlog` column in `kanbans/board.kanban.md` |
| **List tasks** (helm-start) | Read all `###` headings under the target `##` column |
| **Move task** | Cut the task block from one `##` column section, paste under another `##` column section (same file) |
| **Update phase** | Edit the `[phase]` suffix in the `###` heading |
| **Update task** | Edit content within the task block directly |

## Task Block Boundaries

A task block starts at `### Title` (with or without `[phase]`) and ends immediately before the next `###`, `##`, or end of file. When moving or reading tasks, capture the entire block.

## Column Section Boundaries

A column section starts at `## Column Name` and ends immediately before the next `##` or end of file. When inserting a task into a column, append it at the end of the column section (before the next `##`).

## Write Rules

- The board file is **gitignored and local-only**. It is not tracked by git.
  - **Parent worktree / main repo:** full board with all tasks distributed across the 5 columns.
  - **Task worktree** (spawned by `helm-start -w`): board file created by `helm-spawn.ps1` — the spawned task under `## In Progress`, other columns empty (+ any sub-tasks created during work).
  - **Fresh clone:** no board file exists. Run `helm-setup` to create it.
- Each worktree updates its own `kanbans/board.kanban.md`. Never reach into another worktree's filesystem to edit its board.
- Only use extension-supported metadata fields (tags, priority, workload, due, defaultExpanded, steps).
- Descriptions use indented ` ```md ` code blocks — never plain text.
