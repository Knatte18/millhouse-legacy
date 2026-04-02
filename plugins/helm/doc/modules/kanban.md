# Kanban — Local Board

`.kanban.md` is the single source of truth for task tracking. The [kanban.md VS Code extension](https://marketplace.visualstudio.com/items?itemName=wguilherme.kanban-md) renders it as a visual board. GitHub sync is available on demand via `helm-sync`.

For the full file format specification, see [kanban-format.md](kanban-format.md).

## Why .kanban.md

- Zero network dependency — kanban operations work offline.
- VS Code integration — visual board in the editor via the kanban.md extension.
- Plain markdown — readable and editable without tooling.
- Single file — no directory structure, no separate task files. One `.kanban.md` at the repo root.
- Git-tracked — board state follows the branch.
- GitHub sync is decoupled — `helm-sync` pushes state to GitHub Projects when needed.

## Board Columns

4 columns in `.kanban.md`:

| Column | Meaning |
|--------|---------|
| **Backlog** | Task exists, not started |
| **In Progress** | Active work (discussing, planning, implementing, testing, reviewing) |
| **Done** | Completed and committed (or merged) |
| **Blocked** | Needs user input or upstream fix |

## Phase Metadata

Helm's workflow has more granular phases than the 4 board columns. The detailed phase is stored as a `- phase:` metadata line in each task block:

| Phase value | Board column | Meaning |
|-------------|-------------|---------|
| *(not set)* | Backlog | Task exists, not started |
| `discussing` | In Progress | Discussion in progress |
| `planned` | In Progress | Plan approved, ready for `helm-go` |
| `implementing` | In Progress | Code being written |
| `testing` | In Progress | Full verification running |
| `reviewing` | In Progress | Code review in progress |
| `blocked` | Blocked | Needs user input or upstream fix |
| `complete` | Done | Task finished |

Skills update both the board column (move the task block between `##` sections) and the `- phase:` metadata at each transition.

## Setup (helm-setup skill)

One-time per repo. Run `helm-setup` to create `.kanban.md` with Helm columns and `_helm/` directory structure.

## Task Lifecycle

### Creating tasks

Via `helm-add`:
1. Parse title and body from the argument.
2. Add a `### Title` block with metadata under `## Backlog` in `.kanban.md`.

### Reading tasks

`helm-start` reads `.kanban.md`, finds all `###` headings under `## Backlog`. Each heading is a task title. Lists them numbered for user selection.

### Moving tasks between columns

At each phase transition:
1. Updates `- phase:` in the task block's metadata.
2. If the column changes: cuts the entire task block (from `###` heading to just before the next `###` or `##`) and pastes it under the target column heading.

Not every phase change moves the column — e.g. `planned` → `implementing` stays in In Progress (only the phase metadata changes).

### Task identity

Tasks are identified by their `###` heading text. When a task is selected by `helm-start`, its title is stored in `_helm/scratch/status.md` as `task:` for subsequent skills to reference.

## Sub-tasks

Sub-tasks within a task block are tracked as checkbox lists:

```markdown
### My Task
- phase: implementing

- [ ] First sub-task
- [x] Completed sub-task
```

For sub-tasks large enough to warrant independent tracking: create a new `###` entry in `.kanban.md`.

## GitHub Sync (helm-sync)

`helm-sync` is a separate on-demand skill that:
1. Reads `.kanban.md` to get current task states.
2. Creates/updates GitHub issues for tasks that don't have one yet.
3. Updates GitHub Projects board to match local column positions.

GitHub sync is optional. Helm works fully offline using only `.kanban.md`.
