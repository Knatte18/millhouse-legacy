# Directory layout: `.millhouse/`

Mill uses a single `.millhouse/` directory per worktree for all local and shared state.

---

## `.millhouse/` — unified worktree directory

A plain directory at the project root. **Gitignored.** Never committed to the main repo.

```
.millhouse/
  config.local.yaml          ← local-only overrides (model aliases, paths, notifications)
  scratch/                   ← ephemeral files for the current session
    prompt.md                ← hand-off prompts for new threads
    prompt-<slug>.md
    result-<slug>.md
    plans/
    briefs/
    test-baseline.md
  *.py                       ← manual wrapper scripts (optional)
  wiki/                      ← junction → <worktree-parent>/<repo>.wiki/ (shared task state)
  active/                    ← junction → wiki/active/<slug>/ (per-worktree task state)
  <slug>.slug.md             ← identifies the active task for this worktree
```

**What lives in `wiki/` (via junction):**

```
.millhouse/wiki/             ← junction → <parent>/<repo>.wiki/
  Home.md                    ← task list (tasks_md API — never edit directly)
  _Sidebar.md                ← wiki sidebar
  config.yaml                ← shared mill config (committed to wiki)
  proposals/                 ← design documents
  <background-slug>.md       ← per-task background reference docs
  active/
    <slug>/                  ← per-task runtime state
      status.md              ← phase log (append-only via status_md API)
      discussion.md          ← mill-start output
      plan/                  ← mill-plan output
      reviews/               ← reviewer reports
```

**Key rules:**

- `.millhouse/` is gitignored in the main repo. `mill-setup` creates it. `mill-resume` recreates junctions on a new machine.
- `wiki/` and `active/` are junctions — editing files inside them edits the wiki clone directly.
- All writes to shared files (`Home.md`, `config.yaml`) go through `wiki.write_commit_push` with a lock. Per-task files under `active/<slug>/` are written directly, then committed via `wiki.write_commit_push`.
- Every orchestrator entry point calls `wiki.sync_pull(cfg)` before reading wiki state.
- `scratch/` is for ephemeral session files (materialized prompts, merge locks, test baselines). Not cleaned up automatically.
- `config.local.yaml` holds per-machine overrides. It is never committed to the main branch.

---

## Decision table

| Question | `wiki/` (via junction) | `scratch/` | `config.local.yaml` |
|---|---|---|---|
| Travels across machines? | Yes (via wiki git push/pull) | No | No |
| Committed to a branch? | No (wiki is a separate repo) | No | No |
| Shared between worktrees? | Yes (all junctions point at same clone) | No (per-worktree) | No (per-worktree) |
| Lifetime | Persists until explicitly cleaned up | Per-session | Per-worktree |
| Writable by orchestrator? | Via `wiki.write_commit_push` only | Direct file writes | Direct file writes |

---

## Setup

`mill-setup` creates `.millhouse/` on a fresh clone:

1. Clones `<repo>.wiki.git` → `<parent>/<repo>.wiki/`
2. Creates `.millhouse/wiki/` junction → `<parent>/<repo>.wiki/`
3. Creates `.millhouse/active/` junction → `wiki/active/<slug>/` (for the current worktree's task)
4. Creates `.millhouse/config.local.yaml` with local defaults

`mill-resume` (new machine / fresh clone) recreates the junctions and re-clones the wiki if missing.
