---
name: mill-setup
description: Initialize Mill for a repository. Creates kanban boards, config, directory structure, and forwarding wrappers.
---

# mill-setup

One-time initialization per repo. Creates the `_millhouse/` directory structure with config, kanban boards, scratch space, and forwarding wrapper scripts. Idempotent — safe to re-run (skips existing files).

For kanban.md file format details, see `plugins/mill/doc/modules/kanban-format.md`.

---

## Steps

Run these steps in order. Stop on any failure and report the error.

### Step 1: Create directory structure

```bash
mkdir -p _millhouse/scratch/plans _millhouse/scratch/reviews
```

### Step 2: Create .gitignore

If `_millhouse/.gitignore` already exists, skip creation.

If it does not exist, write `_millhouse/.gitignore`:

```
scratch/
*.ps1
```

### Step 3: Create backlog board file

If `_millhouse/backlog.kanban.md` already exists, skip creation (preserves existing backlog data on re-run).

If it does not exist, create it:

```markdown
# <REPO_NAME>

## Backlog

## Spawn

## Delete
```

Validate per `doc/modules/validation.md` (3-column rules: Backlog, Spawn, Delete). If validation fails, report the issue to the user and stop.

### Step 4: Create work board file

If `_millhouse/scratch/board.kanban.md` does not exist, create it:

```markdown
# <REPO_NAME>

## Discussing

## Planned

## Implementing

## Testing

## Reviewing

## Blocked
```

If `_millhouse/scratch/board.kanban.md` already exists with old 5-column structure (detect by presence of `## In Progress`): skip creation but warn: "Existing board.kanban.md uses old format. Delete it and re-run mill-setup to migrate."

Validate per `doc/modules/validation.md` (6-column rules). If validation fails, report the issue to the user and stop.

### Step 5: Write config

**5a: Prompt for repo short-name.**

Ask the user: "Repo short-name for window titles (default: `<directory-name>`):" where `<directory-name>` is the name of the current working directory. If the user provides a value, use it. If the user presses enter or skips, use the directory name. Store the result as `<SHORT_NAME>`.

**5b: Create or upgrade config.**

If `_millhouse/config.yaml` does not exist, write it with the full template below.

If `_millhouse/config.yaml` already exists, check for missing top-level sections and append only the missing ones. Skip sections that already exist (preserves existing values). The sections to check: `git.auto-merge` (under existing `git:` section), `repo:`, `reviews:`. Do not overwrite existing keys.

Full config template (used for new creation):

```yaml
git:
  base-branch: main
  parent-branch: main
  auto-merge: true

repo:
  short-name: "<SHORT_NAME>"
  branch-prefix: ~

reviews:
  discussion: 2
  plan: 3
  code: 3

models:
  session: opus
  plan-review: sonnet
  code-review: sonnet
  plan-fixer: sonnet
  code-fixer: sonnet
  explore: haiku

notifications:
  slack:
    enabled: false
    webhook: ""
    channel: ""
  toast:
    enabled: true
```

Validate `_millhouse/config.yaml` per `doc/modules/validation.md`. If validation fails, report the issue to the user and stop.

### Step 6: Create forwarding wrappers

Create the following forwarding wrappers in `_millhouse/`. For each wrapper, skip creation if the file already exists. If old-named wrappers exist at cwd (`helm-spawn.ps1`, `millhouse-worktree.ps1`, `mill-spawn.ps1`, `fetch-issues.ps1`, `mill-worktree.ps1`), remove them from cwd.

#### 6a: mill-spawn.ps1

Write `_millhouse/mill-spawn.ps1` with the following content:

```powershell
# mill-spawn.ps1 — Forwarding wrapper
# Canonical script: plugins/mill/scripts/mill-spawn.ps1
# This wrapper delegates to the mill plugin in the Claude Code plugin cache.

$PluginBase = Join-Path $env:USERPROFILE ".claude\plugins\cache\millhouse\mill"
if (-not (Test-Path $PluginBase)) {
    Write-Error "Mill plugin not found in cache at: $PluginBase. Install the mill plugin first: claude plugin install mill@millhouse"
    exit 1
}

$VersionDir = Get-ChildItem $PluginBase -Directory |
    Where-Object { $_.Name -match '^\d+\.\d+\.\d+$' } |
    Sort-Object Name -Descending |
    Select-Object -First 1

if (-not $VersionDir) {
    Write-Error "No valid version directory found in: $PluginBase"
    exit 1
}

$Script = Join-Path $VersionDir.FullName "scripts\mill-spawn.ps1"
if (-not (Test-Path $Script)) {
    Write-Error "mill-spawn.ps1 not found at: $Script"
    exit 1
}

& $Script @args
```

#### 6b: fetch-issues.ps1

Write `_millhouse/fetch-issues.ps1` with the following content:

```powershell
# fetch-issues.ps1 — Forwarding wrapper
# Canonical script: plugins/mill/scripts/fetch-issues.ps1
# This wrapper delegates to the mill plugin in the Claude Code plugin cache.

$PluginBase = Join-Path $env:USERPROFILE ".claude\plugins\cache\millhouse\mill"
if (-not (Test-Path $PluginBase)) {
    Write-Error "Mill plugin not found in cache at: $PluginBase. Install the mill plugin first: claude plugin install mill@millhouse"
    exit 1
}

$VersionDir = Get-ChildItem $PluginBase -Directory |
    Where-Object { $_.Name -match '^\d+\.\d+\.\d+$' } |
    Sort-Object Name -Descending |
    Select-Object -First 1

if (-not $VersionDir) {
    Write-Error "No valid version directory found in: $PluginBase"
    exit 1
}

$Script = Join-Path $VersionDir.FullName "scripts\fetch-issues.ps1"
if (-not (Test-Path $Script)) {
    Write-Error "fetch-issues.ps1 not found at: $Script"
    exit 1
}

& $Script @args
```

#### 6c: mill-worktree.ps1

Write `_millhouse/mill-worktree.ps1` with the following content:

```powershell
# mill-worktree.ps1 — Forwarding wrapper
# Canonical script: plugins/mill/scripts/mill-worktree.ps1
# This wrapper delegates to the mill plugin in the Claude Code plugin cache.

$PluginBase = Join-Path $env:USERPROFILE ".claude\plugins\cache\millhouse\mill"
if (-not (Test-Path $PluginBase)) {
    Write-Error "Mill plugin not found in cache at: $PluginBase. Install the mill plugin first: claude plugin install mill@millhouse"
    exit 1
}

$VersionDir = Get-ChildItem $PluginBase -Directory |
    Where-Object { $_.Name -match '^\d+\.\d+\.\d+$' } |
    Sort-Object Name -Descending |
    Select-Object -First 1

if (-not $VersionDir) {
    Write-Error "No valid version directory found in: $PluginBase"
    exit 1
}

$Script = Join-Path $VersionDir.FullName "scripts\mill-worktree.ps1"
if (-not (Test-Path $Script)) {
    Write-Error "mill-worktree.ps1 not found at: $Script"
    exit 1
}

& $Script @args
```

### Step 7: Update CLAUDE.md

If `CLAUDE.md` exists, check for a `## Kanban` section. If the section exists but contains old content (e.g. references to `helm-setup` or `_millhouse/board.kanban.md`), replace the section content with the new template below. If no `## Kanban` section exists, append it.

```markdown
## Kanban

- Backlog board: `_millhouse/backlog.kanban.md` — git-tracked, 3 columns (Backlog, Spawn, Delete). Manual task entry.
- Work board: `_millhouse/scratch/board.kanban.md` — gitignored, 6 phase columns (Discussing through Blocked). Mill-managed. Each worktree gets its own copy (created by mill-spawn).
- Run `mill-setup` to create both board files after a fresh clone (safe to re-run; skips existing files).
- Format reference: `plugins/mill/doc/modules/kanban-format.md`.
- Work board uses columns as phases — no `[phase]` suffix in task headings.
- Only extension-supported metadata fields (priority, tags, workload, due).
- Descriptions use indented ` ```md ` code blocks, never plain text.
```

If `CLAUDE.md` does not exist, create it with these rules.

### Step 8: Report

```
Mill initialized:
  Backlog: _millhouse/backlog.kanban.md (3 columns: Backlog, Spawn, Delete) — git-tracked
  Work board: _millhouse/scratch/board.kanban.md (6 columns: Discussing through Blocked) — gitignored
  Config: _millhouse/config.yaml

Open _millhouse/backlog.kanban.md in VS Code to see the backlog.
Run mill-add to create your first task.
```
