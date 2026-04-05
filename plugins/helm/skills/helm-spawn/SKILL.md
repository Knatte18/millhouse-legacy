---
name: helm-spawn
description: Claim a task from the Spawn column and create a worktree for it.
---

# helm-spawn

Claim a task from the Spawn column and create a worktree for it.

---

## Entry

Read `_helm/config.yaml`. If it does not exist, stop and tell the user to run `helm-setup` first.

Read `kanbans/backlog.kanban.md`. If it does not exist, stop and tell the user to run `helm-setup` first.

---

## Flow

### 1. Find task in Spawn

Read all `###` headings under the `## Spawn` column in `kanbans/backlog.kanban.md`.

- If zero tasks: report "No tasks in Spawn. Drag a task to Spawn first." Stop.
- If one or more: take the **first** task (topmost `###` heading). Capture the full task block (heading through description).

### 2. Create worktree

Determine the current branch: `git branch --show-current`.

Call `helm-spawn.ps1`:

```
pwsh -NoProfile -File "plugins/helm/scripts/helm-spawn.ps1" -TaskTitle "<title>" -TaskBody "<body>" -ParentBranch "<current-branch>"
```

- `-TaskTitle` and `-TaskBody` parameters already exist on the script.
- If the script fails (non-zero exit): report the error and stop. Backlog is unchanged.
- On success: parse the worktree path from the **last line of stdout** (`Write-Output` contract from `helm-spawn.ps1`).

### 3. Update backlog

Remove the task block from the `## Spawn` column in `kanbans/backlog.kanban.md`.

Validate the backlog per `doc/modules/validation.md` (3-column rules: Backlog, Spawn, Delete).

Commit and push:

```
git add kanbans/backlog.kanban.md
git commit -m "spawn: <task-title>"
git push
```

### 4. Write handoff brief

Write `<worktree-path>/_helm/scratch/briefs/handoff.md` using the Handoff Brief Format from `doc/modules/plans.md`:

```markdown
# Handoff: <task title>

## Issue
<task title>

## Parent
Branch: <parent-branch>
Worktree: <parent-path>

## Discussion Summary
<task body from backlog. If no body: just the task title.>

## Knowledge from Parent
<Read _helm/knowledge/ entries. If _helm/knowledge/summary.md exists, use the summary.
If individual entries exist, synthesize relevant ones.
If no knowledge: "No prior knowledge.">

## Config
- Verify: <verify command from _helm/config.yaml or "N/A">
- Dev server: <dev-server command from config, or "N/A">
```

If the task has a GitHub issue number (e.g. from helm-sync import), prefix `## Issue` with `#<number>:`. If no issue number, use title only.

Omit `## Relevant Codeguide Modules` — no explore phase has happened yet. The receiving `helm-start` session will run its own exploration.

### 5. Write status.md

Write `<worktree-path>/_helm/scratch/status.md`:

```
parent: <parent-branch>
task: <task-title>
phase: discussing
```

### 6. Validate work board

Read `<worktree-path>/kanbans/board.kanban.md` (created by `helm-spawn.ps1`).

Validate per `doc/modules/validation.md` (6-column rules: Discussing, Planned, Implementing, Testing, Reviewing, Blocked).

### 7. Report

Tell the user:
- Worktree created at `<path>` on branch `<branch>`
- "Run `helm-start` in the new VS Code window to continue planning."
