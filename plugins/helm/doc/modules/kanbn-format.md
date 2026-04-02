# kanbn Format Reference

Reference for the [kanbn VS Code extension](https://marketplace.visualstudio.com/items?itemName=gordonlarrigan.kanbn) file format. Helm reads and writes these files directly.

Source: [basementuniverse/kanbn](https://github.com/basementuniverse/kanbn)

## Directory Structure

```
.kanbn/
  index.md          # Board: columns + task references
  tasks/            # One .md file per task
    my-task.md
    another-task.md
```

## index.md

YAML frontmatter with board options, followed by a project title (`# heading`), then columns as `## headings`. Each column contains a markdown list of links to task files.

```markdown
---
startedColumns:
  - Implementing
completedColumns:
  - Done
---

# Project Name

## Backlog

- [my-task](tasks/my-task.md)

## Implementing

- [another-task](tasks/another-task.md)

## Done
```

### Rules

- All `## headings` (except `## Options`) are treated as columns.
- Tasks are list items linking to files in `tasks/`: `- [task-id](tasks/task-id.md)`
- `startedColumns`: when a task enters one of these columns, kanbn sets its `started` date.
- `completedColumns`: when a task enters one of these columns, kanbn sets its `completed` date.

### Other options (optional)

| Option | Description |
|--------|-------------|
| `hiddenColumns` | Columns to hide from the board |
| `sprints` | Sprint definitions (`start`, `name`, `description`) |
| `defaultTaskWorkload` | Default workload value |
| `taskWorkloadTags` | Tag-to-workload mapping |
| `columnSorting` | Per-column sort rules |
| `dateFormat` | Display date format |
| `customFields` | Custom metadata fields (`name`, `type`: boolean/date/number/string) |

## Task Files

Stored in `.kanbn/tasks/<task-id>.md`. The task ID is the filename without `.md`.

### Format

```markdown
---
created: 2026-04-02T12:00:00.000Z
updated: 2026-04-02T12:00:00.000Z
assigned: ""
tags: []
---

# Task Name

Description text. Supports full markdown.

## Sub-tasks

- [ ] First sub-task
- [x] Completed sub-task

## Relations

- [duplicates another-task](tasks/another-task.md)

## Comments

- **author** *2026-04-02* Comment text here
```

### Metadata fields

| Field | Type | Description |
|-------|------|-------------|
| `created` | ISO timestamp | Auto-set on creation |
| `updated` | ISO timestamp | Auto-set on modification |
| `tags` | string[] | Task labels |
| `assigned` | string | Assigned user |
| `progress` | number (0-1) | 0 = not started, 1 = complete |
| `started` | ISO timestamp | Set when task enters a `startedColumns` column |
| `completed` | ISO timestamp | Set when task enters a `completedColumns` column |
| `due` | ISO timestamp | Deadline |

### Reserved `## headings`

- `## Sub-tasks` — checkbox list
- `## Relations` — links to other task files
- `## Comments` — author/date/text entries
- `## Metadata` — legacy YAML block (superseded by frontmatter)

## Task ID Convention

The task ID is the filename slug. kanbn generates it from the task name: lowercase, spaces replaced with hyphens, special characters removed. Example: "Add OAuth Support" → `add-oauth-support.md`.

## How Helm Uses kanbn

| Operation | What Helm does |
|-----------|---------------|
| **Create task** (helm-add) | Write `.kanbn/tasks/<id>.md`, add `- [id](tasks/id.md)` under `## Backlog` in index.md |
| **List tasks** (helm-start) | Read index.md, find links under target column |
| **Read task** | Read the linked `.kanbn/tasks/<id>.md` file |
| **Move task** | Remove the `- [id](tasks/id.md)` line from old column, add under new column in index.md |
| **Update task** | Edit the task's `.md` file directly (description, sub-tasks, metadata) |
