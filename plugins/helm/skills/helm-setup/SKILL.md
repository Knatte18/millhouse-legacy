---
name: helm-setup
description: Initialize Helm for a repository. Creates kanban board files, config, and directory structure.
---

# helm-setup

One-time initialization per repo. Creates the `kanbans/` directory with two board files and writes `_helm/config.yaml`.

For kanban.md file format details, see `plugins/helm/doc/modules/kanban-format.md`.

---

## Steps

Run these steps in order. Stop on any failure and report the error.

### Step 1: Create directory structure

```bash
mkdir -p _helm/knowledge _helm/scratch/plans _helm/scratch/briefs kanbans
```

### Step 2: Create backlog board file

If `kanbans/backlog.kanban.md` already exists, skip creation (preserves existing backlog data on re-run).

If it does not exist, create it:

```markdown
# <REPO_NAME>

## Backlog

## Spawn

## Delete
```

Validate per `doc/modules/validation.md` (3-column rules: Backlog, Spawn, Delete). If validation fails, report the issue to the user and stop.

### Step 3: Create work board file

If `kanbans/board.kanban.md` does not exist, create it:

```markdown
# <REPO_NAME>

## Discussing

## Planned

## Implementing

## Testing

## Reviewing

## Blocked
```

If `board.kanban.md` already exists with old 5-column structure (detect by presence of `## In Progress`): skip creation but warn: "Existing board.kanban.md uses old format. Delete it and re-run helm-setup to migrate."

Validate per `doc/modules/validation.md` (6-column rules). If validation fails, report the issue to the user and stop.

### Step 4: Write config

Detect repo info:

```bash
OWNER=$(gh repo view --json owner --jq '.owner.login' 2>/dev/null || echo "")
REPO=$(gh repo view --json name --jq '.name' 2>/dev/null || basename "$(pwd)")
```

Write `_helm/config.yaml`:

```yaml
worktree:
  branch-template: "{parent-branch}-wt-{slug}"
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

Add `_helm/scratch/` and `.scratch/` to `.gitignore` if not already present.

### Step 6: Update CLAUDE.md

If `CLAUDE.md` exists, check for a `## Kanban` section. If the section exists but contains old content (e.g. "single board file with 5 columns"), replace the section content with the new template below. If no `## Kanban` section exists, append it.

```markdown
## Kanban

- Backlog board: `kanbans/backlog.kanban.md` — git-tracked, 3 columns (Backlog, Spawn, Delete). Manual task entry.
- Work board: `kanbans/board.kanban.md` — gitignored, 6 phase columns. Helm-managed. Each worktree gets its own copy (created by helm-spawn).
- Run `helm-setup` to create board files after a fresh clone (safe to re-run; skips existing files).
- Format reference: `plugins/helm/doc/modules/kanban-format.md`.
```

If `CLAUDE.md` does not exist, create it with these rules.

### Step 7: Report

```
Helm initialized:
  Backlog: kanbans/backlog.kanban.md (3 columns: Backlog, Spawn, Delete) — git-tracked
  Work board: kanbans/board.kanban.md (6 columns: Discussing through Blocked) — gitignored
  Config: _helm/config.yaml

Open kanbans/backlog.kanban.md in VS Code to see the backlog.
Run helm-add to create your first task.
```
