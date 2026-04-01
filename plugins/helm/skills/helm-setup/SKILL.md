---
name: helm-setup
description: Initialize Helm for a repository. Creates .kanban.md board, config, and directory structure.
---

# helm-setup

One-time initialization per repo. Creates the `.kanban.md` board with Helm columns and writes `_helm/config.yaml`.

For kanban.md file format details, see `plugins/helm/doc/modules/kanban-format.md`.

---

## Steps

Run these steps in order. Stop on any failure and report the error.

### Step 1: Create directory structure

```bash
mkdir -p _helm/knowledge _helm/scratch/plans _helm/scratch/briefs
```

### Step 2: Create kanban board

If `.kanban.md` does not exist, create it:

```markdown
# <REPO_NAME>

## Backlog

## In Progress

## Done

## Blocked
```

If `.kanban.md` already exists, check that it has all Helm columns (Backlog, In Progress, Done, Blocked). Add any missing columns.

### Step 3: Write config

Detect repo info:

```bash
OWNER=$(gh repo view --json owner --jq '.owner.login' 2>/dev/null || echo "")
REPO=$(gh repo view --json name --jq '.name' 2>/dev/null || basename "$(pwd)")
```

Write `_helm/config.yaml`:

```yaml
worktree:
  branch-template: "{slug}"
  path-template: "../{slug}"

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

### Step 4: Update .gitignore

Add `_helm/scratch/` to `.gitignore` if not already present.

### Step 5: Ask for branch template

Ask the user:

> Branch naming template? Examples: `hanf/{parent-slug}/{slug}` (team repo), `{slug}` (solo repo)

Update `worktree.branch-template` in `_helm/config.yaml` with the user's answer.

### Step 6: Report

```
Helm initialized:
  Board: .kanban.md
  Config: _helm/config.yaml

Open the kanban.md panel in VS Code to see the board.
Run helm-add to create your first task.
```
