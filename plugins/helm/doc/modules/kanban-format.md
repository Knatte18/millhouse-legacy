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

### Task Title
- priority: high
- tags: [tag1, tag2]
- due: 2026-04-02

Description text here.

- [ ] Sub-task 1
- [x] Sub-task 2
```

- `#` — project title (one per file)
- `##` — columns (Backlog, In Progress, Done, Blocked, etc.)
- `###` — tasks within a column

## Columns Helm Uses

| Column | Meaning |
|--------|---------|
| **Backlog** | Task exists, not started |
| **In Progress** | Active work (discussing, implementing, reviewing) |
| **Done** | Completed |
| **Blocked** | Needs user input or upstream fix |

## Task Format

### Minimal task (what helm-add creates)

```markdown
### Add OAuth Support
- created: 2026-04-02
- phase: backlog
```

### Full task

```markdown
### Add OAuth Support
- priority: high
- tags: [auth, backend]
- due: 2026-04-15
- phase: implementing
- created: 2026-04-02

Google OAuth first. Must support token refresh.

- [ ] Create OAuth client
- [x] Set up callback endpoint
```

## Metadata Fields

Metadata lines go directly under the `###` heading, one per line, `- key: value` format.

| Field | Values | Description |
|-------|--------|-------------|
| `priority` | high, medium, low | Colored left border in VS Code |
| `tags` | `[tag1, tag2]` | Labels for filtering |
| `due` | `YYYY-MM-DD` | Deadline |
| `phase` | discussing, planned, implementing, testing, reviewing, blocked, complete | Helm workflow phase (Helm-specific) |
| `created` | `YYYY-MM-DD` | Creation date (Helm-specific) |
| `workload` | Easy, Normal, Hard, Extreme | Effort estimate |

## How Helm Uses .kanban.md

| Operation | What Helm does |
|-----------|---------------|
| **Create task** (helm-add) | Add `### Title` with metadata under `## Backlog` |
| **List tasks** (helm-start) | Read all `###` headings under target column |
| **Move task** | Cut the entire task block (heading through all content until next `###` or `##`), paste under the target column |
| **Update phase** | Edit the `- phase:` line in the task block |
| **Update task** | Edit content within the task block directly |

## Task Block Boundaries

A task block starts at `### Title` and ends immediately before the next `###`, `##`, or end of file. When moving or reading tasks, capture the entire block.

## Task Identity

Tasks are identified by their `###` heading text. When `helm-start` selects a task, the title is stored in `_helm/scratch/status.md` as `task:` for subsequent skills to reference.

Slug for branch names: lowercase, spaces to hyphens, remove special characters. "Add OAuth Support" → `add-oauth-support`.

## Write Rules

- `.kanban.md` is **worktree-local**. Each worktree has its own copy via git.
  - **Parent worktree / main repo:** full board with all tasks.
  - **Task worktree** (spawned by `helm-start -w`): board with only the spawned task (+ any sub-tasks created during work).
- Each worktree updates its own `.kanban.md`. Never reach into another worktree's filesystem to edit its board.
- On merge (`helm-merge`): `.kanban.md` will conflict — always keep the **parent's version** (`--theirs` during merge parent→worktree, parent's copy during merge worktree→parent). Then update the parent's board (move task to Done).
- Keep metadata lines in consistent order: created, phase, priority, tags, due.
- Descriptions and sub-tasks go after the metadata lines, separated by a blank line.
