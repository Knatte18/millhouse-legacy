# kanban.md Format Reference

Reference for the [kanban.md VS Code extension](https://marketplace.visualstudio.com/items?itemName=wguilherme.kanban-md) file format. Helm reads and writes `.kanban.md` directly.

Source: [wguilherme/kanban.md](https://github.com/wguilherme/kanban.md)

## File Location

Single file at the repo root: `.kanban.md`. No subdirectories, no separate task files.

The file must use the `.kanban.md` extension to be recognized by the VS Code extension.

## Structure

```markdown
# Project Name

## Column Name

### Task Title [phase]
- priority: high
- tags: [tag1, tag2]

Description text here.
```

- `#` — project title (one per file)
- `##` — columns (Backlog, In Progress, Done, Blocked, etc.)
- `###` — tasks within a column, optionally with `[phase]` suffix

## Columns Helm Uses

| Column | Meaning |
|--------|---------|
| **Backlog** | Task exists, not started |
| **In Progress** | Active work (discussing, implementing, reviewing) |
| **Done** | Completed |
| **Blocked** | Needs user input or upstream fix |

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

Google OAuth first. Must support token refresh.
```

## Metadata Fields

Only use fields supported by the kanban.md extension. Unknown fields are rendered as list items, not metadata.

| Field | Values | Description |
|-------|--------|-------------|
| `priority` | high, medium, low | Colored left border in VS Code (red/yellow/green) |
| `tags` | `[tag1, tag2]` | Labels shown on card |
| `due` | `YYYY-MM-DD` | Deadline |
| `workload` | Easy, Normal, Hard, Extreme | Effort estimate |

Do NOT use `- created:` or `- phase:` as metadata lines — they are not recognized by the extension and will render as separate list items. Phase is tracked in the `###` heading.

## How Helm Uses .kanban.md

| Operation | What Helm does |
|-----------|---------------|
| **Create task** (helm-add) | Add `### Title [backlog]` under `## Backlog` |
| **List tasks** (helm-start) | Read all `###` headings under target column |
| **Move task** | Cut the entire task block (heading through all content until next `###` or `##`), paste under the target column |
| **Update phase** | Edit the `[phase]` suffix in the `###` heading |
| **Update task** | Edit content within the task block directly |

## Task Block Boundaries

A task block starts at `### Title` (with or without `[phase]`) and ends immediately before the next `###`, `##`, or end of file. When moving or reading tasks, capture the entire block.

## Write Rules

- `.kanban.md` is **worktree-local**. Each worktree has its own copy via git.
  - **Parent worktree / main repo:** full board with all tasks.
  - **Task worktree** (spawned by `helm-start -w`): board with only the spawned task (+ any sub-tasks created during work).
- Each worktree updates its own `.kanban.md`. Never reach into another worktree's filesystem to edit its board.
- On merge (`helm-merge`): `.kanban.md` will conflict — always keep the **parent's version** (`--theirs` during merge parent→worktree, parent's copy during merge worktree→parent). Then update the parent's board (move task to Done).
- Only use extension-supported metadata fields (priority, tags, due, workload).
- Descriptions go after metadata lines, separated by a blank line.
