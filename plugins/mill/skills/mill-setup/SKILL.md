---
name: mill-setup
description: Initialize Mill for a repository. Creates tasks.md, config, directory structure, and forwarding wrappers.
---

# mill-setup

One-time initialization per project. Bootstraps the orphan `tasks` branch and persistent tasks worktree, creates `_millhouse/` directory structure with config, scratch space, forwarding wrapper scripts, and VS Code color settings. Idempotent — safe to re-run (skips existing files).

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

### Step 3: Preserve pre-migration tasks.md (if present)

If `tasks.md` exists at the project root (pre-migration repo), leave it in place — Step 3b will use it as the orphan seed and a subsequent commit on the parent branch will remove it.

If `tasks.md` does not exist at the project root, do nothing here. Step 3b will seed the orphan branch with `# Tasks\n`.

### Step 3b: Bootstrap tasks branch and worktree

This step ensures the `tasks` orphan branch and its worktree both exist. Idempotent.

Resolve: let `<repo-toplevel>` = `git rev-parse --show-toplevel`; let `<reponame>` = the basename of `<repo-toplevel>`; let `<tasks-wt>` = `<parent of repo-toplevel>/<reponame>.worktrees/tasks` (forward slashes).

1. **Check remote branch existence:** run `git ls-remote --heads origin tasks`. If it prints a matching ref, the branch exists on remote — run `git fetch origin tasks` to create the local tracking ref, then skip to step 4.
2. **Check local branch existence:** run `git branch --list tasks`. If present, the branch exists locally — skip to step 3 (push if needed).
3. **Create orphan locally:** in a scratch detached worktree at `<parent-of-repo>/<reponame>.worktrees/orphan-bootstrap` (`git worktree add --detach <scratch-path>`), run:
   - `git checkout --orphan tasks`
   - `git rm -rf . --quiet`
   - Write `tasks.md` — seed with the content of `<repo-toplevel>/tasks.md` if it exists, else `# Tasks\n`. Use forward-slash paths.
   - Write `.gitignore` with exactly:
     ```
     .mill-tasks.lock
     .vscode/
     ```
   - `git add tasks.md .gitignore`
   - `git commit -m "init tasks branch: tasks.md + .gitignore"`
   - `git push -u origin tasks`
   - `git worktree remove <scratch-path>` (cleanup)
   - **Push-race handling:** if `git push -u origin tasks` fails with `rejected` / `non-fast-forward` (another machine won the race), run `git fetch origin tasks`, then proceed from step 4.
4. **Check worktree existence:** run `git worktree list --porcelain` and look for a line `worktree <tasks-wt>`. If present, skip step 5.
5. **Create the persistent tasks worktree:** `git worktree add <tasks-wt> tasks`.

### Step 4: Write config

**4a: Prompt for repo short-name.**

Ask the user: "Repo short-name for window titles (default: `<directory-name>`):" where `<directory-name>` is the name of the current working directory. If the user provides a value, use it. If the user presses enter or skips, use the directory name. Store the result as `<SHORT_NAME>`.

**4b: Create or migrate config.**

If `_millhouse/config.yaml` does not exist, write it with the full `pipeline:`-schema template.

If `_millhouse/config.yaml` already exists, check for the presence of a top-level `pipeline:` block:
- **Present:** the config is already in the new schema. Check `git.auto-merge`, `git.require-pr-to-base`, `repo:`, and `notifications:` sections exist; append any missing ones without overwriting. Also check for new v3 pipeline keys: `pipeline.plan-review.holistic`, `pipeline.plan-review.per-card`, `pipeline.code-review.holistic`, `pipeline.code-review.per-card`, and `runtime.pre-arm-timeout-seconds`; append any missing ones with default values without overwriting existing values. Also check for the self-reinforcement-loop keys: `notifications.auto-report.enabled` (default `false`), `revise.brevity-threshold-lines` (default `5`), and `revise.brevity-threshold-chars` (default `500`). Append any missing ones with their default values. **Insertion strategy for nested keys** (text-based — no YAML library): for `notifications.auto-report.enabled`, locate the `notifications:` block by line-prefix match (`^notifications:`) and insert an `auto-report:` sub-block (with `enabled: false` indented 4 spaces under `auto-report:`, which is itself indented 2 spaces under `notifications:`) immediately after the `notifications:` line if absent; preserve the existing `slack:` and `toast:` siblings verbatim. For `revise.*`, append the entire `revise:` top-level block at the end of the file if absent. Preserve everything else verbatim. No further migration.
- **Absent:** the config is pre-W1 legacy. Run the per-key migration below (Step 4c — legacy-to-pipeline migration).

**Template (used for new creation and as the migration target shape):** Read `plugins/mill/templates/millhouse-config.yaml`, substitute `<SHORT_NAME>` with the value from Step 4a, `<IMPLEMENTER>` with `sonnet`, and `<TASKS_WORKTREE_PATH>` with the absolute path `<parent-of-repo-root>/<reponame>.worktrees/tasks` (using forward slashes / `as_posix()`). Example: `C:/Code/millhouse.worktrees/tasks`. Then write to `_millhouse/config.yaml`. Only block-style YAML — the hand-written parser at `plugins/mill/scripts/millpy/core/config.py` does not support inline flow mappings.

When **appending missing keys** to an existing config, also append a `tasks.worktree-path:` key if absent. Locate the line immediately after the `repo:` block end (first blank line after the repo block, or the first top-level key after `repo:`) and insert:
```yaml
tasks:
  worktree-path: <tasks-wt>
```
If any part of the `tasks:` block is already present, skip without modifying it. This preserves existing user edits.

**Step 4c — legacy-to-pipeline migration (runs only when the existing config has no `pipeline:` block).**

Migration is text-based line manipulation, not YAML-library round-trip. millpy has **no `yaml` / `pyyaml` dependency** — `millpy/core/config.py` is a hand-written minimal parser that only understands block-style YAML. The migration agent must NOT `Import-Module powershell-yaml` or `import yaml` at any point.

**Before writing:** copy `_millhouse/config.yaml` to `_millhouse/config.yaml.bak`. Skip if `.bak` already exists.

**Extraction pass.** Use the millpy config loader (`python -c "from millpy.core.config import load; ..."`) to read the legacy file into a dict. Pull these values with sensible fallbacks:
- `pipeline.implementer` ← legacy `models.implementer` (fallback: `sonnet`)
- `pipeline.discussion-review.default` ← legacy `review-modules.discussion.default` → `models.discussion-review.default` → fallback `sonnetmax` (MUST be a tool-use reviewer; discussion-review never runs bulk-mode workers)
- `pipeline.plan-review.default` → fallback `sonnet`
- `pipeline.code-review.default` → fallback `sonnet`
- `pipeline.discussion-review.rounds` → fallback `2`
- `pipeline.plan-review.rounds` → fallback `3`
- `pipeline.code-review.rounds` → fallback `3`

If `pipeline:` block is missing, read `plugins/mill/templates/millhouse-config.yaml`, substitute `<IMPLEMENTER>` with the resolved implementer name (from the extraction pass above, fallback `sonnet`), substitute `<SHORT_NAME>` with the value from Step 4a, and write the result to `_millhouse/config.yaml` as the source of truth for the pipeline schema. The template already contains `g25flash`-based reviewer names; do NOT hardcode reviewer names in this SKILL file.

**Validation note.** After writing, reload the file via `millpy.core.config.load` and call `millpy.core.config.resolve_reviewer_name(cfg, "plan", 1, slice_type="per-card")` as a smoke test. A `ConfigError` from the resolver indicates an edge case — stop with the error and tell the user to inspect `_millhouse/config.yaml` manually.

**Step 4d — tasks.md marker migration.**

Resolve `tasks.md` via `millpy.tasks.tasks_md.resolve_path(cfg)` (where `cfg` is the freshly written config). If resolution fails (tasks worktree not yet bootstrapped or config missing `tasks.worktree-path`), skip Step 4d silently. Otherwise, scan the resolved `tasks.md` for any `## [>] Title` headings. For each match, rewrite to `## [s] Title`. If any matches were found and rewritten, use `millpy.tasks.tasks_md.write_commit_push(cfg, new_content, "chore: migrate [>] markers to [s]")` to commit and push. If no matches, no write occurs (idempotent).

Rationale: older millhouse installations may have live `[>]` markers in their `tasks.md`. After the `[s]` vocabulary change landed, `[>]` markers are invalid (rejected by `tasks_md.validate()`) and invisible to the new picker. This migration step keeps upgrades non-destructive across installations.

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
| `_millhouse/mill-color.py` | `set_worktree_color` |

**Plugin-cache junction check (detect-only, never mutate).** After writing the wrappers, check whether `%USERPROFILE%\.claude\plugins\cache\millhouse\mill` exists and resolves to a readable directory. If missing or dangling, print a warning line (NOT a hard error) telling the user to run the symlink-plugins repair script (`symlink-plugins` in the millhouse repo checkout) to repair it. **Do not modify the junction** — this is explicit user policy. No `New-Item -ItemType Junction`, no `Remove-Item` against the junction path.

### Step 6: Write VS Code settings

**Invariant: the main worktree is always green (`#2d7d46`).** Child worktrees exclude green from their palette by design — see `_pick_worktree_color` / `_MAIN_WORKTREE_COLOR` in [plugins/mill/scripts/millpy/entrypoints/spawn_task.py](../../scripts/millpy/entrypoints/spawn_task.py). The green titleBar is how the developer tells the main worktree apart from child worktrees at a glance.

The step is idempotent against re-runs. Use the logic below, not a blanket "skip if exists":

1. **`.vscode/settings.json` does not exist** → create `.vscode/` directory. Read `plugins/mill/templates/vscode-settings.json`, substitute `<COLOR_HEX>` with `#2d7d46`, `<SHORT_NAME>` with the value from Step 4a (`repo.short-name` from `_millhouse/config.yaml`, guaranteed to exist by the prior config-write step), and `<SLUG>` with `${activeEditorShort}`, then write to `.vscode/settings.json`.

2. **`.vscode/settings.json` exists with `titleBar.activeBackground == "#2d7d46"`** → no-op. The invariant already holds.

3. **`.vscode/settings.json` exists with a non-green `titleBar.activeBackground`** → back up the current file to `.vscode/settings.json.bak` in the same directory (overwrite any pre-existing `.bak`), then overwrite `settings.json` from the template as in case 1. The `.bak` is transient — not explicitly gitignored, but developers can delete it safely.

Do not rotate the main worktree through the child palette; green is hardcoded. Do not change the `<SLUG>` substitution (currently `${activeEditorShort}`) — VS Code resolves this dynamically.

### Step 7: Update CLAUDE.md

Read `plugins/mill/templates/claude-md-sections.md` (the `## Startup` + `## Tasks` content; no tokens to substitute — strip the leading HTML comment before writing).

If `CLAUDE.md` exists, check for a `## Kanban` or `## Tasks` section. If either section exists, replace its content with the template body. If neither exists, append the template body. Also check for a `## Startup` section — if missing, add it before `## Tasks`.

If `CLAUDE.md` does not exist, create it with these rules.

### Step 8: Report

```
Mill initialized:
  Tasks: tasks.md on orphan branch 'tasks' (worktree at <tasks-wt>)
  Status: _millhouse/task/status.md (phase tracking + timeline)
  Config: _millhouse/config.yaml
  Git: _millhouse/ is gitignored — local to each clone/worktree

Open the tasks worktree in VS Code to edit tasks.md, or run mill-add.
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
