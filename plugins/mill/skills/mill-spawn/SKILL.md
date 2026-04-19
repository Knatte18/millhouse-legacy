---
name: mill-spawn
description: Add a task to Home.md and create a worktree for it in one command.
---

# mill-spawn

One-shot. Add a task with `[s]` marker to `Home.md` (the wiki task list), commit and push it to the wiki, then call `spawn_task.py` to claim it and create a worktree.

For Home.md (tasks.md) file format details, see `plugins/mill/doc/formats/tasksmd.md`.

**Sync invariant:** mill-spawn MUST call `wiki.sync_pull(cfg)` before presenting task choices so the task list reflects remote state.

---

## Usage

```
mill-spawn <title>: <body>
mill-spawn <title>
```

Text before the first colon is the title. Text after is the body (description). No colon means title only.

---

## Phases

### Phase 1: Verify setup

If `.millhouse/config.local.yaml` (or the legacy `.millhouse/config.yaml`) does not exist, stop and tell the user to run `mill-setup` first.

If the `.millhouse/wiki/` junction does not exist at cwd, stop and tell the user to run `mill-setup` first (the wiki junction is required for task state).

### Phase 2: Sync wiki

Call `wiki.sync_pull(cfg)` to refresh the local wiki clone from remote. This ensures the task list shown to the user reflects the current state across all machines and worktrees.

### Phase 3: Parse input

Split the argument on the first `:` character.

- Left side (trimmed) → task title
- Right side (trimmed) → task description (may be empty)

### Phase 4: Add task with spawn marker

Read `Home.md` from `.millhouse/wiki/Home.md`. Append a new task block at the end of the file with the `[s]` marker:

If no description:

```markdown
## [s] <Title>
```

If description provided:

```markdown
## [s] <Title>
- <Description>
```

### Phase 5: Validate

Validate `Home.md` per `plugins/mill/doc/formats/validation.md` (tasksmd structural rules). If validation fails, report the issue and stop.

### Phase 6: Write to wiki

Write the updated `Home.md` to the wiki and push via `tasks_md.write_commit_push(cfg, new_content, f"task: spawn {title}")`. This call:
1. Acquires the wiki lock (shared-write path).
2. Writes `Home.md` to the wiki clone.
3. Commits and pushes.
4. Releases the lock.

If `LockBusy` is raised, retry once after a brief wait, then fail with a message to the user.

### Phase 7: Call spawn_task.py

Locate `spawn_task.py` using three-tier resolution:

1. **Forwarding wrapper:** `.millhouse/mill-spawn.py` (written by `mill-setup`, resolves the plugin-cache path at runtime)
2. **Plugin source** (works in the millhouse repo itself): `<repo-root>/plugins/mill/scripts/spawn_task.py`
3. **Plugin cache** (works in any repo with mill plugin installed): `~/.claude/plugins/cache/millhouse/mill/<latest-version>/scripts/spawn_task.py`

Run via bash:

```bash
python "<resolved-path>"
```

The script performs the following (card 8 logic):

1. `wiki.sync_pull(cfg)` — refresh wiki before reading Home.md.
2. Acquire wiki lock.
3. Read `Home.md`, find the first `[s]` task, resolve slug via `tasks_md.parse` + `paths.slug_from_branch` semantics (slugify the task heading).
4. Mark the entry `[active]` in `Home.md` via `tasks_md.write_commit_push`.
5. Release wiki lock.
6. Create the feature worktree via `git worktree add -b <branch-name> <worktrees-dir>/<slug>`.
7. Write initial `status.md` at `<new-worktree>/.millhouse/wiki/active/<slug>/status.md` by rendering `plugins/mill/templates/status-discussing.md` (which already contains `phase: discussing` in YAML and a `discussing` entry in Timeline). Do NOT call `append_phase` on the freshly-rendered file. After the template write, the spawn script calls `wiki.write_commit_push(cfg, [f"active/{slug}/status.md"], f"task: init {slug}")`.
8. Regenerate sidebar via the `regenerate_sidebar` entrypoint.

**Slug derivation:** The slug is derived from the current branch name via `paths.slug_from_branch(cfg)`. This strips the optional `repo.branch-prefix/` (e.g. `"mh"` strips `"mh/"` from `"mh/foo-task"`). The branch name is set to `<branch-prefix>/<slug>` if a prefix is configured, or `<slug>` otherwise.

**Active task directory:** `<new-worktree>/.millhouse/wiki/active/<slug>/` — contains `status.md`, `discussion.md`, `plan/`, `reviews/`.

**No `.millhouse/children/` registry:** child tracking is replaced by the wiki's `active/<slug>/` directory structure. No junction is created in a `children/` folder.

**`.millhouse/` copy-on-spawn:** When spawning, the script copies `.millhouse/` (excluding `task/`, `scratch/`, and `children/`) from the parent worktree to the new worktree, so the new worktree inherits `config.local.yaml` and wrapper scripts.

### Phase 8: Report

Report the worktree path and branch name from the script output. The last line of stdout is the project path.

```
Spawned: <title>
  Branch: <branch-name>
  Path:   <project-path>

Run mill-start in the new worktree window to begin planning.
```

---

## Select task from Home.md

When `spawn_task.py` enters numbered-picker mode (no `[s]` task exists), it presents a numbered list of unmarked tasks from Home.md:

```
Pick a task:
  1) <Title A>
  2) <Title B>
Pick a task number:
```

The user types a number. The selected task is claimed and the worktree is created. Empty mode (no pickable tasks) prints a hint to run `mill-add` or `mill-spawn <title>`.

---

## Error Conditions

| Condition | Action |
|---|---|
| `.millhouse/config.local.yaml` missing | Stop, tell user to run `mill-setup` |
| `.millhouse/wiki/` junction missing | Stop, tell user to run `mill-setup` |
| `wiki.sync_pull` fails | Report error; do not proceed (stale state risk) |
| `LockBusy` on write | Retry once, then fail with message |
| `tasks_md.validate` fails | Report issue and stop before pushing |
| `git worktree add` fails | Report error with stderr |
