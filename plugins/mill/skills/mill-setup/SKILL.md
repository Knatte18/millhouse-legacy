---
name: mill-setup
description: Initialize Mill for a repository. Creates tasks.md, config, directory structure, and forwarding wrappers.
---

# mill-setup

One-time initialization per project. Creates `tasks.md` in the project root (the working directory where `_millhouse/` is being created), the `_millhouse/` directory structure with config, scratch space, forwarding wrapper scripts, and VS Code color settings. Idempotent — safe to re-run (skips existing files).

For tasks.md file format details, see `plugins/mill/doc/modules/tasksmd-format.md`.

---

## Steps

Run these steps in order. Stop on any failure and report the error.

### Step 1: Create directory structure

```bash
mkdir -p _millhouse/scratch/reviews
mkdir -p _millhouse/task/reviews
```

### Step 2: Add gitignore entries for local state

Check the repo's root `.gitignore` for an entry matching `**/_millhouse/`. If not present, append it. If already present, skip.

### Step 3: Create tasks.md

If `tasks.md` already exists in the project root, skip creation (preserves existing task data on re-run).

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

If `_millhouse/config.yaml` already exists, check for missing top-level sections and append only the missing ones. Skip sections that already exist (preserves existing values). The sections to check: `git.auto-merge` (under existing `git:` section), `git.require-pr-to-base` (under existing `git:` section), `repo:`, `reviews:`. Do not overwrite existing keys.

**Important exception for `models:`:** the "skip sections that already exist" short-circuit applies to all top-level sections **except** `models:`. The `models:` block has a per-key migration step (Step 4b — `models:` block migration, below) that inspects and updates individual sub-keys regardless of whether the `models:` block is already present. This is necessary because the schema for `models:` changed in this task (per-round reviewer slots, new `implementer` and `discussion-review` slots), and existing installs need their `models:` block updated in place rather than skipped.

Full config template (used for new creation):

```yaml
git:
  base-branch: main
  parent-branch: main
  auto-merge: false
  require-pr-to-base: false

repo:
  short-name: "<SHORT_NAME>"
  branch-prefix: ~

reviews:
  discussion: 2
  plan: 3
  code: 3

models:
  session: opus
  implementer: sonnet
  explore: haiku
  discussion-review:
    default: opus
  plan-review:
    default: sonnet
  code-review:
    default: sonnet

notifications:
  slack:
    enabled: false
    webhook: ""
    channel: ""
  toast:
    enabled: true
```

**Step 4b — `models:` block migration (runs every time mill-setup is invoked).**

When `_millhouse/config.yaml` exists, read the existing `models:` block and migrate it in place to the new shape. This runs regardless of whether the `models:` block is already present (the per-key inspection is idempotent on conformant configs).

Migration rules:

1. **Required scalar keys** (`session`, `implementer`, `explore`):
   - If missing, append the key under `models:` with the default value: `session: opus`, `implementer: sonnet`, `explore: haiku`.
   - If present, leave alone.

2. **Per-round object keys** (`discussion-review`, `plan-review`, `code-review`):
   - **Absent:** insert as `<key>:` followed by indented `default: <default-value>`. Defaults: `discussion-review` → `opus`; `plan-review` → `sonnet`; `code-review` → `sonnet`.
   - **Scalar value** (e.g. `plan-review: sonnet`): rewrite to `<key>:` followed by indented `default: <existing-scalar-value>`. The user's existing scalar choice is preserved as the new `default` sub-key.
   - **Object with `default` sub-key:** leave alone (already conformant).
   - **Object missing `default` sub-key:** insert `default: <hardcoded-default>` under it.

3. **Print a diff of what changed.** Use simple `before:` / `after:` lines per modified key — no fancy diff format. Example:
   ```
   models.plan-review:
     before: sonnet
     after: {default: sonnet}
   models.implementer:
     before: (missing)
     after: sonnet
   ```

4. **Write the updated content back to `_millhouse/config.yaml`.** No git commit (`_millhouse/` is gitignored).

**Implementation guidance for the agent doing the migration step at run time:** prefer a YAML round-trip parser if available. Check availability via `Get-Command ConvertFrom-Yaml -ErrorAction SilentlyContinue` — if the result is null, the `powershell-yaml` module is absent. **Never use `Import-Module powershell-yaml` unconditionally** — it errors on machines where the module is not installed. If no YAML library is available, fall back to **inline string editing of the file**: locate the `models:` block by line range, replace each key surgically. Do not rewrite the entire file from scratch — that would lose comments and unrelated sections.

**Validation note.** After migration completes, mill-setup must call the entry-time validation rules from `doc/modules/validation.md` `## _millhouse/config.yaml` section. Validation failure after migration is a hard error — it indicates an edge case the migration could not handle. Stop with the validation error and tell the user to inspect `_millhouse/config.yaml` manually.

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

#### 5d: mill-terminal.ps1

Write `_millhouse/mill-terminal.ps1` with the following content:

```powershell
# mill-terminal.ps1 — Forwarding wrapper
# Canonical script: plugins/mill/scripts/mill-terminal.ps1
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

$Script = Join-Path $VersionDir.FullName "scripts\mill-terminal.ps1"
if (-not (Test-Path $Script)) {
    Write-Error "mill-terminal.ps1 not found at: $Script"
    exit 1
}

& $Script @args
```

#### 5e: mill-vscode.ps1

Write `_millhouse/mill-vscode.ps1` with the following content:

```powershell
# mill-vscode.ps1 — Forwarding wrapper
# Canonical script: plugins/mill/scripts/mill-vscode.ps1
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

$Script = Join-Path $VersionDir.FullName "scripts\mill-vscode.ps1"
if (-not (Test-Path $Script)) {
    Write-Error "mill-vscode.ps1 not found at: $Script"
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

If `CLAUDE.md` exists, check for a `## Kanban` or `## Tasks` section. If either section exists, replace the section content with the new template below. If neither section exists, append it. Also check for a `## Startup` section — if missing, add it before `## Tasks`.

```markdown
## Startup
On first message in a conversation, invoke `mill:conversation` and `mill:workflow` before responding.

## Tasks

- Task list: `tasks.md` in project root — git-tracked, `## ` headings for tasks, optional `[phase]` markers.
- Phase tracking: `_millhouse/task/status.md` — `phase:` field is the authoritative source. `## Timeline` section records chronological phase history.
- `_millhouse/` is gitignored. On spawn, it is copied (excluding `task/`, `scratch/`, and `children/`) from parent to new worktree.
- Run `mill-setup` to initialize after a fresh clone (safe to re-run; skips existing files).
- Format reference: `plugins/mill/doc/modules/tasksmd-format.md` (tasks.md format).
```

If `CLAUDE.md` does not exist, create it with these rules.

### Step 8: Report

```
Mill initialized:
  Tasks: tasks.md (git-tracked, ## headings for tasks)
  Status: _millhouse/task/status.md (phase tracking + timeline)
  Config: _millhouse/config.yaml
  Git: _millhouse/ is gitignored — local to each clone/worktree

Edit tasks.md to add tasks, or run mill-add.
Run mill-start to pick a task and begin.
```

### Step 9: Backfill junctions for active children

This step runs after all other setup steps. It is idempotent and best-effort — any per-entry failure is a warning, not a fatal error.

1. Check if `_millhouse/children/` exists. If not, skip this step.

2. Run `git worktree list --porcelain` and parse the output into a map of `<branch-name> → <worktree-path>`. Strip the `refs/heads/` prefix from branch names.

3. For each `.md` file in `_millhouse/children/*.md`:
   - Parse the YAML frontmatter for `branch:` and `status:`.
   - If `status:` is NOT `active` AND NOT `pr-pending`: skip this entry. Terminal-status entries do not get junctions.
   - Derive the slug: strip the leading `<timestamp>-` prefix from the `.md` filename (or use the final segment of the `branch:` value after any `/` prefix).
   - Compute `$junctionPath = Join-Path $childrenDir $slug`.
   - If `$junctionPath` already exists as a reparse point: check if it points at `<worktree-path>/_millhouse/task/`. If correct, skip (idempotent). If stale, delete via `(Get-Item $junctionPath).Delete()` and re-create.
   - If the worktree path is not in the map from step 2: log a warning "Backfill skipped for `$slug`: no matching worktree found" and continue.
   - Otherwise compute `$targetPath = Join-Path $worktreePath "_millhouse/task"`. If the target does not exist: log a warning "Backfill skipped for `$slug`: target `$targetPath` does not exist — run mill-setup in that worktree first" and continue.
   - Create the junction: `New-Item -ItemType Junction -Path $junctionPath -Target $targetPath`.

4. Log a summary of created junctions (e.g., "Backfilled 1 junction: `add-functionality-to`").
