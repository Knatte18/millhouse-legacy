---
name: helm-setup
description: Initialize Helm for a repository. Creates kanban board file, config, and directory structure.
---

# helm-setup

One-time initialization per repo. Creates the `kanbans/` directory with a single board file and writes `_helm/config.yaml`.

For kanban.md file format details, see `plugins/helm/doc/modules/kanban-format.md`.

---

## Steps

Run these steps in order. Stop on any failure and report the error.

### Step 1: Create directory structure

```bash
mkdir -p _helm/knowledge _helm/scratch/plans _helm/scratch/briefs kanbans
```

### Step 2: Create kanban board file

If `kanbans/board.kanban.md` does not exist, create it. Do not overwrite an existing file.

```markdown
# <REPO_NAME>

## Backlog

## Spawn

## In Progress

## Done

## Blocked
```

Validate the board file per `doc/modules/validation.md`. If validation fails, report the issue to the user and stop.

### Step 3: Write config

Detect repo info:

```bash
OWNER=$(gh repo view --json owner --jq '.owner.login' 2>/dev/null || echo "")
REPO=$(gh repo view --json name --jq '.name' 2>/dev/null || basename "$(pwd)")
```

Write `_helm/config.yaml`:

```yaml
models:
  session: opus
  plan-review: sonnet
  code-review: sonnet
  explore: haiku

notifications:
  slack:
    enabled: false
    webhook: ""
    channel: ""
  toast:
    enabled: true
```

No `github:` section by default. GitHub integration is optional --- run `helm-sync` to set it up when needed.

### Step 4b: Validate config

Validate `_helm/config.yaml` per `doc/modules/validation.md`. If validation fails, report the issue to the user and stop.

### Step 3b: Create `_git/config.yaml`

If `_git/config.yaml` does not exist, create it:

```yaml
base-branch: main
parent-branch: ~
```

Create the `_git/` directory if needed. This provides the initial git config for `spawn-worktree.ps1` to read `base-branch` from.

### Step 4: Update .gitignore

Add `_helm/scratch/`, `.scratch/`, and `_git/` to `.gitignore` if not already present.

### Step 5: Update CLAUDE.md

If `CLAUDE.md` exists, append the following rules under a `## Kanban` section (if not already present):

```markdown
## Kanban

- Task board: `kanbans/board.kanban.md` — single board file with 5 columns (kanban.md VS Code extension). Gitignored and local-only.
- Batch related small changes into one commit. Don't commit trivial edits individually.
```

If `CLAUDE.md` does not exist, create it with these rules.

### Step 6: Report

```
Helm initialized:
  Board: kanbans/board.kanban.md (5 columns: Backlog, Spawn, In Progress, Done, Blocked)
  Config: _helm/config.yaml
  Git config: _git/config.yaml

Open kanbans/board.kanban.md in VS Code to see the board.
Run helm-add to create your first task.
```
