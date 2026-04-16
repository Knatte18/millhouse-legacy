---
name: mill-setup
description: Initialize Mill for a repository. Creates tasks.md, config, directory structure, and forwarding wrappers.
---

# mill-setup

One-time initialization per project. Creates `tasks.md` in the project root (the working directory where `_millhouse/` is being created), the `_millhouse/` directory structure with config, scratch space, forwarding wrapper scripts, and VS Code color settings. Idempotent — safe to re-run (skips existing files).

For tasks.md file format details, see `plugins/mill/doc/formats/tasksmd.md`.

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

**4b: Create or migrate config.**

If `_millhouse/config.yaml` does not exist, write it with the full `pipeline:`-schema template.

If `_millhouse/config.yaml` already exists, check for the presence of a top-level `pipeline:` block:
- **Present:** the config is already in the new schema. Check `git.auto-merge`, `git.require-pr-to-base`, `repo:`, and `notifications:` sections exist; append any missing ones without overwriting. Also check for new v3 pipeline keys: `pipeline.plan-review.holistic`, `pipeline.plan-review.per-card`, `pipeline.code-review.holistic`, `pipeline.code-review.per-card`, and `runtime.pre-arm-timeout-seconds`; append any missing ones with default values without overwriting existing values. Preserve everything else verbatim. No further migration.
- **Absent:** the config is pre-W1 legacy. Run the per-key migration below (Step 4c — legacy-to-pipeline migration).

**Template (used for new creation and as the migration target shape):** Read `plugins/mill/templates/millhouse-config.yaml`, substitute `<SHORT_NAME>` with the value from Step 4a and `<IMPLEMENTER>` with `sonnet`, then write to `_millhouse/config.yaml`. Only block-style YAML — the hand-written parser at `plugins/mill/scripts/millpy/core/config.py` does not support inline flow mappings.

**Step 4c — legacy-to-pipeline migration (runs only when the existing config has no `pipeline:` block).**

Migration is text-based line manipulation, not YAML-library round-trip. millpy has **no `yaml` / `pyyaml` dependency** — `millpy/core/config.py` is a hand-written minimal parser that only understands block-style YAML. The migration agent must NOT `Import-Module powershell-yaml` or `import yaml` at any point.

**Before writing:** copy `_millhouse/config.yaml` to `_millhouse/config.yaml.bak`. Skip if `.bak` already exists.

**Extraction pass.** Use the millpy config loader (`python -c "from millpy.core.config import load; ..."`) to read the legacy file into a dict. Pull these values with sensible fallbacks:
- `pipeline.implementer` ← legacy `models.implementer` (fallback: `sonnet`)
- `pipeline.discussion-review.default` ← legacy `review-modules.discussion.default` → `models.discussion-review.default` → fallback `g3flash-x3-sonnetmax`
- `pipeline.plan-review.default` → fallback `g3flash-x3-sonnetmax`
- `pipeline.code-review.default` → fallback `g3flash-x3-sonnetmax`
- `pipeline.discussion-review.default` → fallback `sonnetmax`
- `pipeline.discussion-review.rounds` → fallback `2`
- `pipeline.plan-review.rounds` → fallback `3`
- `pipeline.code-review.rounds` → fallback `3`

If `pipeline:` block is missing, create it with the fallback values:

```yaml
pipeline:
  implementer: sonnet
  discussion-review:
    rounds: 2
    default: sonnetmax
  plan-review:
    rounds: 3
    default: g3flash-x3-sonnetmax
    holistic: sonnetmax
    per-card: g3flash
  code-review:
    rounds: 3
    default: g3flash-x3-sonnetmax
    holistic: g3flash-x3-g3flash
    per-card: g3flash

runtime:
  pre-arm-timeout-seconds: 14400
```

**Validation note.** After writing, reload the file via `millpy.core.config.load` and call `millpy.core.config.resolve_reviewer_name(cfg, "plan", 1, slice_type="per-card")` as a smoke test. A `ConfigError` from the resolver indicates an edge case — stop with the error and tell the user to inspect `_millhouse/config.yaml` manually.

### Step 5: Create forwarding wrappers

Generate five `.py` forwarding wrappers in `_millhouse/`. Each delegates to the corresponding entrypoint in the mill plugin cache, with runtime semver discovery (no hardcoded version).

**Cleanup first.** Remove any legacy wrappers from `_millhouse/`: `.ps1` files (PowerShell-era: `mill-spawn`, `mill-worktree`, `mill-terminal`, `mill-vscode`, `fetch-issues`, plus historical variants `helm-spawn`, `millhouse-worktree`) and `.cmd` files (`mill-spawn.cmd`, `mill-worktree.cmd`, `mill-terminal.cmd`, `mill-vscode.cmd`, `fetch-issues.cmd`). Also remove any such legacy wrappers at cwd with matching names.

**Template.** Read `plugins/mill/templates/wrapper.py`. For each wrapper, substitute `<ENTRYPOINT>` with the entrypoint module name and write to `_millhouse/`. Skip creation if the file already exists with the correct content.

| Wrapper file | `<ENTRYPOINT>` |
|---|---|
| `_millhouse/mill-spawn.py` | `spawn_task` |
| `_millhouse/fetch-issues.py` | `fetch_issues` |
| `_millhouse/mill-worktree.py` | `worktree` |
| `_millhouse/mill-terminal.py` | `open_terminal` |
| `_millhouse/mill-vscode.py` | `open_vscode` |

**Plugin-cache junction check (detect-only, never mutate).** After writing the wrappers, check whether `%USERPROFILE%\.claude\plugins\cache\millhouse\mill` exists and resolves to a readable directory. If missing or dangling, print a warning line (NOT a hard error) telling the user to run the symlink-plugins repair script (`symlink-plugins` in the millhouse repo checkout) to repair it. **Do not modify the junction** — this is explicit user policy. No `New-Item -ItemType Junction`, no `Remove-Item` against the junction path.

### Step 6: Write VS Code settings

If `.vscode/settings.json` already exists, skip (preserves existing color settings on re-run).

If it does not exist, create `.vscode/` directory. Read `plugins/mill/templates/vscode-settings.json`, substitute `<COLOR_HEX>` with `#2d7d46`, `<SHORT_NAME>` with the value from Step 4a, and `<SLUG>` with `${activeEditorShort}`, then write to `.vscode/settings.json`.

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
- Format reference: `plugins/mill/doc/formats/tasksmd.md` (tasks.md format).
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
