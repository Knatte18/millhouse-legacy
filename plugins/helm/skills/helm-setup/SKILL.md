---
name: helm-setup
description: Initialize Helm for a repository. Creates kanban board files, config, and directory structure.
---

# helm-setup

One-time initialization per repo. Creates the `kanbans/` directory with separate board files and writes `_helm/config.yaml`.

For kanban.md file format details, see `plugins/helm/doc/modules/kanban-format.md`.

---

## Steps

Run these steps in order. Stop on any failure and report the error.

### Step 1: Create directory structure

```bash
mkdir -p _helm/knowledge _helm/scratch/plans _helm/scratch/briefs kanbans
```

### Step 2: Create kanban board files

If `kanbans/` does not contain all 4 board files, create the missing ones. Do not overwrite existing files.

Each file follows the same template — `# <REPO_NAME>` title and one `##` column heading:

**`kanbans/backlog.kanban.md`:**
```markdown
# <REPO_NAME>

## Backlog
```

**`kanbans/processing.kanban.md`:**
```markdown
# <REPO_NAME>

## In Progress
```

**`kanbans/done.kanban.md`:**
```markdown
# <REPO_NAME>

## Done
```

**`kanbans/blocked.kanban.md`:**
```markdown
# <REPO_NAME>

## Blocked
```

Validate all board files per `doc/modules/validation.md`. If validation fails, report the issue to the user and stop.

### Step 3: Ask for branch template

Ask the user:

> Branch naming template? Examples: `{parent-branch}-wt-{slug}` (default), `{slug}` (solo repo). Variables: `{parent-branch}` (full branch name), `{repo-name}` (repo dir name), `{slug}` (task slug, max 20 chars).

### Step 4: Write config

Detect repo info:

```bash
OWNER=$(gh repo view --json owner --jq '.owner.login' 2>/dev/null || echo "")
REPO=$(gh repo view --json name --jq '.name' 2>/dev/null || basename "$(pwd)")
```

Write `_helm/config.yaml` using the branch template from step 3:

```yaml
worktree:
  branch-template: "<user's answer from step 3>"
  path-template: "../{repo-name}-worktrees/{slug}"

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

### Step 5: Update .gitignore

Add `_helm/scratch/` to `.gitignore` if not already present.

### Step 6: Report

```
Helm initialized:
  Board: kanbans/ (4 board files)
  Config: _helm/config.yaml

Open any .kanban.md file in VS Code to see its board.
Run helm-add to create your first task.
```
