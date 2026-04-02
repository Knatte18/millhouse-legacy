# kanbn VS Code Extension — User Guide

How to use the [kanbn extension](https://marketplace.visualstudio.com/items?itemName=gordonlarrigan.kanbn) alongside Helm.

## Installation

1. Open VS Code Extensions view (`Ctrl+Shift+X`).
2. Search for `kanbn`.
3. Install "Kanbn Extension for Visual Studio Code" by Gordon Larrigan.

No CLI installation needed — the extension is self-contained.

## First Use

If `.kanbn/index.md` already exists (created by `helm-setup`), the extension picks it up automatically.

If not: click the kanbn item in the status bar → it will offer to initialise. But prefer running `helm-setup` so the board gets Helm's columns.

## Opening the Board

- **Status bar**: click the kanbn item at the bottom of VS Code. It shows task counts (total / started / completed).
- **Command palette**: `Ctrl+Shift+P` → `Kanbn: Open board`.

## Working with Tasks

### On the board

- **Drag tasks** between columns to move them.
- **Click a task title** to open the task editor in a new tab.
- **Create tasks** using the board UI, or via `Kanbn: Add task` in the command palette.

Helm skills (helm-add, helm-start, helm-go) also create and move tasks by editing the files directly. The board updates automatically when files change.

### Editing task files directly

Task files live in `.kanbn/tasks/<task-id>.md`. You can edit them in any editor. The board refreshes when the file changes.

### Filtering

The board has a filter input at the top-right. Enter a filter string and press Enter.

| Filter | What it matches |
|--------|----------------|
| `text` | Task ID and name |
| `assigned:name` | Assigned user |
| `tag:label` | Task tags |
| `description:text` | Description and sub-tasks |
| `overdue` | Tasks with due date in the past |
| `comment:text` | Comment author or text |
| `subtask:text` | Sub-task text |
| `relation:text` | Relation type or related task ID |

Filters are case-insensitive. Multiple terms are AND-combined.

Example: `assigned:henrik tag:helm` shows tasks assigned to henrik with the "helm" tag.

### Custom fields

Helm uses a `phase` custom field to track detailed workflow phase. You can filter on it:

- `phase:planned` — tasks with approved plans
- `phase:reviewing` — tasks in code review
- `phase:blocked` — tasks waiting on input

## Sprints and Burndown

Optional features, not used by Helm but available:

- **Sprints**: enable the sprint button in settings (`kanbn.showSprintButton: true`). Start a sprint from the board.
- **Burndown chart**: `Kanbn: Open burndown chart` in the command palette. Enable the button with `kanbn.showBurndownButton: true`.

## Settings

Open VS Code Settings (`Ctrl+,`) and search for `kanbn`:

| Setting | Default | Description |
|---------|---------|-------------|
| `kanbn.showUninitialisedStatusBarItem` | true | Show status bar item even before init |
| `kanbn.showTaskNotifications` | true | Notifications on task create/update/delete |
| `kanbn.showSprintButton` | false | Show sprint button above the board |
| `kanbn.showBurndownButton` | false | Show burndown chart button |

## Custom Styling

Create `.kanbn/board.css` to override board styles. The extension supports light, dark, and high-contrast themes out of the box.

## How It Interacts with Helm

Helm and the kanbn extension share the same files. Both can read and write — changes from either side are reflected immediately.

| Action | Helm does it | Extension does it |
|--------|-------------|-------------------|
| Create task | `helm-add` | Board UI / command palette |
| Move between columns | Skills edit `index.md` | Drag on board |
| Edit task details | Skills edit task `.md` file | Task editor tab |
| View board | `helm-status` (terminal) | Visual board in VS Code |
| Archive completed tasks | Not implemented | `Kanbn: Archive tasks` |

The extension is the visual interface. Helm is the automation layer. They don't conflict.
