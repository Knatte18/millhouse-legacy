# Directory layout: `.mill/` vs `_millhouse/`

Mill uses two directories per worktree. They have different scopes, lifetimes, and git visibility.

---

## `.mill/` — shared wiki state

A junction (Windows) or symlink (Unix) pointing at the local wiki clone (`<project-parent>/<repo>.wiki/`). Every worktree in the project gets its own `.mill/` junction pointing at the same clone.

**What lives here:**

```
.mill/                          ← junction → <parent>/<repo>.wiki/
  Home.md                       ← task list (tasks_md API — never edit directly)
  _Sidebar.md                   ← wiki sidebar
  config.yaml                   ← shared mill config (committed to wiki)
  reviewers.yaml                ← reviewer recipes (committed to wiki)
  proposals/                    ← design documents
  <background-slug>.md          ← per-task background reference docs
  active/
    <slug>/                     ← per-task runtime state
      status.md                 ← phase log (append-only via status_md API)
      discussion.md             ← mill-start output
      plan/                     ← mill-plan output
      reviews/                  ← reviewer reports
```

**Key rules:**
- `.mill/` itself is gitignored and not committed to the main repo. `mill-setup` creates it; `mill-resume` recreates it on a new machine.
- All writes to shared files (`Home.md`, `config.yaml`, `reviewers.yaml`) go through `wiki.write_commit_push` with a lock. Per-task files under `active/<slug>/` are written directly, then committed via `write_commit_push`.
- Every orchestrator entry point calls `wiki.sync_pull(cfg)` before reading wiki state.

---

## `_millhouse/` — local worktree state

A plain directory at the project root (or project sub-root in nested layouts). **Gitignored.** Never committed, never shared across machines.

**What lives here:**

```
_millhouse/
  config.local.yaml             ← local-only overrides (model aliases, paths)
  task/                         ← active task working files (this worktree only)
    implementer-brief-instance.md
    discussion.md               ← copy/working draft (source of truth is .mill/active/<slug>/)
    plan.md
    reviews/
  scratch/                      ← ephemeral files for the current session
    prompt.md                   ← hand-off prompts for new threads
    prompt-<slug>.md
    result-<slug>.md
    plans/
    briefs/
```

**Key rules:**
- Everything here is single-machine, single-worktree. It does not travel with the branch.
- `scratch/` is for files that only matter within one session (materialized prompts, merge locks, test baselines). They are not cleaned up automatically.
- `_millhouse/` must be in the repo-root `.gitignore`.

---

## Decision table

| Question | `.mill/` | `_millhouse/` |
|---|---|---|
| Travels across machines? | Yes (via wiki git push/pull) | No |
| Committed to a branch? | No (wiki is a separate repo) | No |
| Shared between worktrees? | Yes (all junctions point at same clone) | No (per-worktree) |
| Lifetime | Persists until explicitly cleaned up | Per-session or per-task |
| Writable by orchestrator? | Via `wiki.write_commit_push` only | Direct file writes |

---

## Setup

`mill-setup` creates both:
1. Clones `<repo>.wiki.git` → `<parent>/<repo>.wiki/`
2. Creates `.mill/` junction → `<parent>/<repo>.wiki/`
3. Creates `_millhouse/` directory with `config.local.yaml`

`mill-resume` (new machine / fresh clone) recreates the junction and re-clones the wiki if missing.
