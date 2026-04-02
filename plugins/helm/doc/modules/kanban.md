# Kanban — Local kanbn Board

`.kanbn/index.md` is the single source of truth for task tracking. The [kanbn VS Code extension](https://marketplace.visualstudio.com/items?itemName=gordonlarrigan.kanbn) renders it as a visual board. GitHub sync is available on demand via `helm-sync`.

## Why Local kanbn

- Zero network dependency — kanban operations work offline.
- VS Code integration — visual board in the editor via the kanbn extension.
- Plain markdown — readable and editable without tooling.
- Git-tracked — board state follows the branch. Each worktree gets its own board state.
- GitHub sync is decoupled — `helm-sync` pushes state to GitHub Projects when needed.

## Board Structure

One `.kanbn/index.md` per repo (or per worktree). Columns:

| Column | Meaning |
|--------|---------|
| **Backlog** | Task exists, not started |
| **Discussing** | `helm-start` claimed the task, discussion in progress |
| **Planned** | Plan approved, ready for `helm-go` |
| **Implementing** | `helm-go` is executing |
| **Reviewing** | Code review in progress |
| **Blocked** | Needs user input or upstream fix |
| **Done** | Completed and committed (or merged) |

## File Format

`.kanbn/index.md` uses the kanbn markdown format:

```markdown
---
startedColumns:
  - Implementing
completedColumns:
  - Done
---

# Millhouse

## Backlog

- Task title one
- Task title two

## Discussing

## Planned

- Task with plan ready

## Implementing

## Reviewing

## Blocked

## Done

- Completed task
```

Tasks are markdown list items (`- Task title`) under column headings. Task descriptions and metadata can optionally live in `.kanbn/tasks/<task-id>.md` files (managed by the kanbn extension), but Helm reads and writes task entries directly in `index.md`.

## Setup (helm-setup skill)

One-time per repo. Run `helm-setup` to create `.kanbn/index.md` with Helm columns and `_helm/` directory structure.

## Task Lifecycle

### Creating tasks

Via `helm-add`:
1. Parse title and body from the argument.
2. Add `- <title>` under `## Backlog` in `.kanbn/index.md`.

### Reading tasks

`helm-start` reads `.kanbn/index.md`, finds all list items under `## Backlog`. Lists them numbered for user selection.

### Moving tasks between columns

At each phase transition, CC edits `.kanbn/index.md`:
1. Remove the `- <task>` line from its current column.
2. Add the `- <task>` line under the target column heading.

This is a simple text edit — read the file, find the task line, move it.

### Task identity

Tasks are identified by their title text in `index.md`. When a task is selected by `helm-start`, its title is stored in `_helm/scratch/status.md` as `task:` for subsequent skills to reference.

## Sub-tasks

Tasks within a worktree that are too small for their own board entry can be tracked as a checklist in the plan file. For sub-tasks large enough to warrant independent tracking: add them as separate entries in `.kanbn/index.md`.

## GitHub Sync (helm-sync)

`helm-sync` is a separate on-demand skill that:
1. Reads `.kanbn/index.md` to get current task states.
2. Creates/updates GitHub issues for tasks that don't have one yet.
3. Updates GitHub Projects board to match local column positions.
4. Posts plan summaries and progress comments on linked issues.

GitHub sync is optional. Helm works fully offline using only `.kanbn/index.md`.
