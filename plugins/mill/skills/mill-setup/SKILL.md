---
name: mill-setup
description: Initialize Mill for a repository. Creates tasks.md, config, directory structure, and forwarding wrappers.
---

# mill-setup

One-time initialization per repo. Creates `tasks.md` at the repo root, the `_millhouse/` directory structure with config, scratch space, forwarding wrapper scripts, and VS Code color settings. Idempotent — safe to re-run (skips existing files).

For tasks.md file format details, see `plugins/mill/doc/modules/backlog-format.md`.

---

## Steps

Run these steps in order. Stop on any failure and report the error.

### Step 1: Create directory structure

```bash
mkdir -p _millhouse/scratch/reviews
```

### Step 2: Add gitignore entries for local state

Check the repo's root `.gitignore` for an entry matching `**/_millhouse/`. If not present, append it. If already present, skip.

### Step 3: Create tasks.md

If `tasks.md` already exists at the repo root, skip creation (preserves existing task data on re-run).

If it does not exist, create it:

```markdown
# Tasks
```

After creating, stage, commit, and push:

```bash
git add tasks.md
git commit -m "chore: initialize tasks.md"
git push
```

Validate per `doc/modules/validation.md` (tasks.md structural rules). If validation fails, report the issue to the user and stop.

### Step 4: Write config

**4a: Prompt for repo short-name.**

Ask the user: "Repo short-name for window titles (default: `<directory-name>`):" where `<directory-name>` is the name of the current working directory. If the user provides a value, use it. If the user presses enter or skips, use the directory name. Store the result as `<SHORT_NAME>`.

**4b: Create or upgrade config.**

If `_millhouse/config.yaml` does not exist, write it with the full template below.

If `_millhouse/config.yaml` already exists, check for missing top-level sections and append only the missing ones. Skip sections that already exist (preserves existing values). The sections to check: `git.auto-merge` (under existing `git:` section), `repo:`, `reviews:`. Do not overwrite existing keys.

Full config template (used for new creation):

```yaml
git:
  base-branch: main
  parent-branch: main
  auto-merge: false

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

### Step 5: Create forwarding wrappers

Create the following forwarding wrappers in `_millhouse/`. For each wrapper, skip creation if the file already exists. If old-named wrappers exist at cwd (`helm-spawn.ps1`, `millhouse-worktree.ps1`, `mill-spawn.ps1`, `fetch-issues.ps1`, `mill-worktree.ps1`), remove them from cwd.

#### 5a: mill-spawn.ps1

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

#### 5b: fetch-issues.ps1

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

#### 5c: mill-worktree.ps1

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

### Step 6: Write VS Code settings

If `.vscode/settings.json` already exists, skip (preserves existing color settings on re-run).

If it does not exist, create `.vscode/` directory and write `.vscode/settings.json`:

```json
{
    "workbench.colorCustomizations": {
        "titleBar.activeBackground": "#2d7d46",
        "titleBar.activeForeground": "#ffffff",
        "titleBar.inactiveBackground": "#2d7d46",
        "titleBar.inactiveForeground": "#ffffffaa"
    },
    "window.title": "<SHORT_NAME> — ${activeEditorShort}"
}
```

Where `<SHORT_NAME>` is the value from Step 4a.

### Step 7: Update CLAUDE.md

If `CLAUDE.md` exists, check for a `## Kanban` or `## Tasks` section. If either section exists, replace the section content with the new template below. If neither section exists, append it.

```markdown
## Tasks

- Task list: `tasks.md` at repo root — git-tracked, `## ` headings for tasks, optional `[phase]` markers.
- Phase tracking: `_millhouse/scratch/status.md` — `phase:` field is the authoritative source. `## Timeline` section records chronological phase history.
- `_millhouse/` is gitignored. On spawn, it is copied (excluding `scratch/`) from parent to new worktree.
- Run `mill-setup` to initialize after a fresh clone (safe to re-run; skips existing files).
- Format reference: `plugins/mill/doc/modules/backlog-format.md` (tasks.md format).
```

If `CLAUDE.md` does not exist, create it with these rules.

### Step 8: Report

```
Mill initialized:
  Tasks: tasks.md (git-tracked, ## headings for tasks)
  Status: _millhouse/scratch/status.md (phase tracking + timeline)
  Config: _millhouse/config.yaml
  Git: _millhouse/ is gitignored — local to each clone/worktree

Edit tasks.md to add tasks, or run mill-add.
Run mill-start to pick a task and begin.
```
