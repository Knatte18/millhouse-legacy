---
name: mill-setup
description: Initialize Mill for a repository. Creates wiki clone, junction, config, directory structure, and forwarding wrappers. Idempotent — safe to re-run.
---

# mill-setup

One-time initialization (and idempotent re-run) per project. Bootstraps the GitHub Wiki clone as the central task hub, creates the `.millhouse/wiki/` junction, splits config into shared (wiki) and local (`.millhouse/`) files, and migrates from the legacy orphan-branch layout when detected.

For tasks.md (Home.md) file format details, see `plugins/mill/doc/formats/tasksmd.md`.

---

## Overview

The new task system uses the repo's GitHub Wiki as the shared state store. Each worktree has a `.millhouse/wiki/` junction pointing at a local wiki clone (`<project-parent>/<repo>.wiki/`). Per-task runtime state lives in `.millhouse/wiki/active/<slug>/`. Config is split: shared settings in `.millhouse/wiki/config.yaml` (committed to the wiki), local-only settings in `.millhouse/config.local.yaml` (gitignored).

**Migration trigger:** if `.millhouse/config.yaml` exists and contains `tasks.worktree-path`, the repo is on the legacy orphan-branch layout — mill-setup performs the config split and wiki bootstrap migration automatically.

---

## Phases

Run each phase in order. Stop on the first hard error and report it. Each phase checks current state before acting — every step is idempotent.

### Phase 1: Validate wiki readiness

1. **Derive wiki URL.** Run `git remote get-url origin` from cwd. Compute wiki URL: replace the trailing `.git` with `.wiki.git`; if no `.git` suffix, append `.wiki.git`. Example: `https://github.com/org/myrepo.git` → `https://github.com/org/myrepo.wiki.git`.

2. **Check wiki enabled.** Run `gh api repos/<owner>/<repo> --jq .has_wiki`. If the result is `false`, halt:
   ```
   Enable the wiki for this repo on GitHub (Settings → Features → Wikis), then re-run mill-setup.
   ```

3. **Check wiki is non-empty.** Run `git ls-remote <wiki-url>`. If the command fails (exit non-zero), halt:
   ```
   The wiki is empty. Open https://github.com/<owner>/<repo>/wiki and create the Home page, then re-run mill-setup.
   ```
   (GitHub does not create the wiki git repo until the first page is saved.)

### Phase 2: Clone or pull the wiki

1. Compute the wiki clone path via `millpy.core.paths.wiki_clone_path(cfg)`. Default: `<project-parent>/<repo>.wiki/` (e.g. `C:/Code/myrepo.wiki/`).

2. **If the target does not exist:** run `git clone <wiki-url> <target>`.

3. **If the target exists and is a git repo** (`.git` directory or `HEAD` file present): run `git -C <target> pull --ff-only`.

4. **If the target exists but is NOT a git repo:** halt with a clear error — do not overwrite or delete user data.

### Phase 3: Create `.millhouse/wiki/` junction

1. Compute junction path: `<cwd>/.millhouse/wiki`.

2. **If the junction does not exist:** create it via `millpy.core.junction.create(target=<wiki-clone-path>, link_path=<junction-path>)`.

3. **If the junction already exists and points at the correct wiki clone:** skip (idempotent).

4. **If the junction exists but points at a different target:** halt with:
   ```
   .millhouse/wiki/ junction exists but points at <current-target>. Expected <wiki-clone-path>. Remove .millhouse/wiki/ and re-run.
   ```

### Phase 4: Config split (migration or fresh setup)

#### 4a — Migration path (legacy config detected)

**Trigger:** `.millhouse/config.yaml` exists AND contains `tasks.worktree-path`.

1. **Backup first.** Copy `.millhouse/config.yaml` to `.millhouse/config.yaml.bak` BEFORE any write. Skip the backup if `.bak` already exists (a prior interrupted migration).

2. **Split into two files:**
   - `<wiki-clone>/config.yaml` — shared settings: `git`, `repo`, `pipeline` (strip `holistic:` and `per-card:` keys — replaced by single holistic reviewer per card 5), `runtime`, `revise` blocks. Drop any `reviewers:` block — reviewer recipes live in Python (`reviewers/definitions.py` + `workers.py`).
   - `.millhouse/config.local.yaml` — machine-specific settings: `notifications`, and `wiki:` (only if `clone-path` was non-default).

3. **Commit and push wiki file** via `millpy.tasks.wiki.write_commit_push(cfg, ["config.yaml"], "chore: mill-setup config split")`.

4. **Only after the push succeeds:** delete `.millhouse/config.yaml`.

5. **On push failure:** restore `.millhouse/config.yaml` from `.bak` and halt:
   ```
   Config split aborted — wiki push failed. Restored from backup. Check network and re-run.
   ```

6. **Idempotent re-entry cleanup:** on a subsequent successful mill-setup run (`.millhouse/wiki/config.yaml` present in the wiki clone), remove `.millhouse/config.yaml.bak` if it still exists.

#### 4b — Fresh setup path (no legacy config)

If `.millhouse/config.yaml` does NOT exist and `.millhouse/config.local.yaml` does NOT exist:

1. **Prompt for repo short-name.** Ask: "Repo short-name for window titles (default: `<directory-name>`):" If the user provides a value, use it. If the user skips, use the directory name.

2. **Write local config.** Create `.millhouse/config.local.yaml` with `notifications:` block (platform defaults).

3. **Write shared config to wiki.** Read `plugins/mill/templates/millhouse-config.yaml`, substitute `<SHORT_NAME>`, and write to `<wiki-clone>/config.yaml`. Commit and push via `wiki.write_commit_push(cfg, ["config.yaml"], "chore: mill-setup init config")`.

### Phase 5: Bootstrap wiki contents

Check and create missing standard wiki files. Each write uses `wiki.write_commit_push`.

1. **Home.md.** If `<wiki-clone>/Home.md` does not exist, write:
   ```markdown
   # Tasks

   ```
   (A single `# Tasks` heading and a trailing newline.) Commit message: `"chore: init Home.md"`.

2. **`_Sidebar.md`.** If missing, invoke the `regenerate_sidebar` entrypoint to generate it from Home.md.

3. **`.gitignore`.** If missing in the wiki clone, write `.mill-lock` as the single line (the lock file must never be committed). Commit message: `"chore: add wiki .gitignore"`.

### Phase 6: Directory structure and wrappers

1. **Create local directories:**
   ```bash
   mkdir -p .millhouse/scratch/reviews
   mkdir -p .millhouse/task/reviews
   ```

2. **Add `.gitignore` entry.** Check the repo's root `.gitignore` for an entry matching `**/.millhouse/`. If absent, append it.

3. **Create forwarding wrappers.** Generate `.py` forwarding wrappers in `.millhouse/`. Read `plugins/mill/templates/wrapper.py`, substitute `<ENTRYPOINT>`, and write. Skip if the file already exists with the correct content.

   | Wrapper file | `<ENTRYPOINT>` |
   |---|---|
   | `.millhouse/mill-spawn.py` | `spawn_task` |
   | `.millhouse/fetch-issues.py` | `fetch_issues` |
   | `.millhouse/mill-worktree.py` | `worktree` |
   | `.millhouse/mill-terminal.py` | `open_terminal` |
   | `.millhouse/mill-vscode.py` | `open_vscode` |
   | `.millhouse/mill-color.py` | `set_worktree_color` |

   **Legacy cleanup.** Remove any `.ps1` and `.cmd` wrappers from `.millhouse/` (PowerShell-era: `mill-spawn`, `mill-worktree`, `mill-terminal`, `mill-vscode`, `fetch-issues`, `helm-spawn`, `millhouse-worktree`).

4. **Plugin-cache junction check (detect-only).** Check whether `%USERPROFILE%\.claude\plugins\cache\millhouse\mill` resolves to a readable directory. If missing or dangling, print a warning (not a hard error): tell the user to run `symlink-plugins` from the millhouse repo to repair it. **Do not modify the junction** — user policy.

### Phase 7: VS Code settings

**Invariant: the main worktree is always green (`#2d7d46`).** Child worktrees exclude green from their palette — see `_pick_worktree_color` in `spawn_task.py`.

1. **`.vscode/settings.json` does not exist** → create `.vscode/`. Read `plugins/mill/templates/vscode-settings.json`, substitute `<COLOR_HEX>` with `#2d7d46`, `<SHORT_NAME>` with `repo.short-name` from config, and `<SLUG>` with `${activeEditorShort}`. Write to `.vscode/settings.json`.

2. **`.vscode/settings.json` exists with `titleBar.activeBackground == "#2d7d46"`** → no-op.

3. **`.vscode/settings.json` exists with a non-green `titleBar.activeBackground`** → back up to `.vscode/settings.json.bak`, then overwrite from template as in case 1.

### Phase 8: Update CLAUDE.md

Read `plugins/mill/templates/claude-md-sections.md` (the `## Startup` + `## Tasks` content; strip the leading HTML comment before writing).

- If `CLAUDE.md` exists: check for a `## Kanban` or `## Tasks` section. If either exists, replace its content. If neither exists, append. Ensure a `## Startup` section exists before `## Tasks`.
- If `CLAUDE.md` does not exist: create it with these sections.

### Phase 9: Report

On successful completion, print:

```
mill-setup complete. Wiki cloned at <wiki-clone-path>. Junction at <cwd>/.millhouse/wiki

  Tasks (Home.md): .millhouse/wiki/Home.md
  Config (shared): .millhouse/wiki/config.yaml
  Config (local):  .millhouse/config.local.yaml
  Active tasks:    .millhouse/wiki/active/<slug>/

Migrations performed: <list or "none">
Run mill-start to pick a task and begin.
```

---

## Idempotency

Every phase checks current state before acting. Re-running mill-setup after a partial run is always safe:

- Wiki already cloned → pulls latest changes.
- `.millhouse/wiki/` junction already correct → skipped.
- Config already split → skipped; `.bak` removed if wiki files are confirmed present.
- Home.md already exists → skipped.
- Wrappers already present with correct content → skipped.

---

## Error Conditions

| Condition | Action |
|---|---|
| `has_wiki: false` | Halt with instructions to enable wiki on GitHub |
| Wiki empty (ls-remote fails) | Halt with URL to create first page |
| Wiki clone target exists but not a git repo | Halt — do not overwrite |
| `.millhouse/wiki/` junction points at wrong target | Halt with remove-and-rerun instructions |
| Config split push fails | Restore from `.bak`, halt |
| Plugin-cache junction missing | Warn only — do not halt |
