# Codeguide Architecture

## Prerequisites

Installed globally via `./install-local.sh` or `claude plugin install codeguide@millhouse`.

Per-repo setup via `/codeguide-setup` to create the `_codeguide/` skeleton.

---

## Skills

### Initialization

| Skill | Purpose |
|---|---|
| `/codeguide-setup` | All setup: first-time root init, root refresh, subfolder activation. Detects context automatically. |

### Doc maintenance

| Skill | Weight | Scope | What it does |
|---|---|---|---|
| `/codeguide-generate` | Heavy | User-specified `[project] [module-path]` | Creates docs for undocumented source files. Full source scan. |
| `/codeguide-maintain` | Heavy | User-specified `[project] [module-path]` | Fixes existing docs: content accuracy, structural violations, pointers, links, local-rules compliance. Full source + doc comparison. |
| `/codeguide-update` | Light | Git diff (default), `1h`, `3d`, `HEAD~3`, or explicit files | Combines generate + sync, but only for files in scope. Creates missing docs AND fixes stale docs. Safe for commit-time use (called by mill-commit). |

### Review

| Skill | Purpose |
|---|---|
| `/review-navigation` | Reviews violation logs in `_codeguide/runtime/navigation-issues.md`. Shows patterns of routing bypasses for guide improvement. |

---

## Hooks (deactivated by default)

Hook scripts are included but not active. To re-enable, restore `hooks.json` from the source files (`hooks-base.json`, `hooks-enforcement.json`, `hooks-violation-logging.json`) using `_merge_hooks.py`.

| Hook | Event | Purpose |
|---|---|---|
| `base_inject_routing.py` | UserPromptSubmit, SubagentStart | Inject routing instructions — "read Overview.md first" |
| `enforce_init_session.py` | UserPromptSubmit | Create turn-scoped session state |
| `enforce_track_read.py` | PreToolUse (Read) | Track when Overview is read |
| `enforce_track_search.py` | PreToolUse (Grep/Glob/Bash) | Block searches until Overview read |
| `enforce_stop.py` | Stop | Clean up session state, log parity issues |
| `audit_track_task.py` | PreToolUse (Agent) | Count subagent spawns |
| `audit_track_subagent.py` | SubagentStart | Count subagent injections |

---

## Shared scripts

| Script | Purpose |
|---|---|
| `scripts/_resolve.py` | Two-tier path resolution. Routing files resolve from cwd. Metadata files walk up to nearest ancestor (stops at `.git/`). Also callable as CLI: prints the metadata `_codeguide/` path. |
| `hooks/_merge_hooks.py` | Composes `hooks.json` from base files (`hooks-base.json`, `hooks-enforcement.json`, `hooks-violation-logging.json`). |

---

## File ownership

| File | Owner | Overwritten on reload? |
|---|---|---|
| `_codeguide/modules/DocumentationGuide.md` | Plugin | Yes |
| `_codeguide/NavigationHooks.md` | Plugin | Yes |
| `_codeguide/cgignore.md` | User | No (created from template) |
| `_codeguide/config.yaml` | User | No (new keys merged) |
| `_codeguide/local-rules.md` | User | No |
| `_codeguide/cgexclude.md` | User | No |
| `_codeguide/Overview.md` | User | No |
| `_codeguide/modules/*.md` | User | No |
| `_codeguide/root.txt` | Generated | Recreated by setup |

---

## Typical workflows

**First-time setup:**
1. `/codeguide-setup .py`
2. `/codeguide-generate`

**Subfolder activation:**
1. `/codeguide-setup` (from subfolder)

**Plugin update:**
1. Run `./install-local.sh` (refreshes cache)
2. `/codeguide-setup` (refreshes plugin-owned files)

**Routine maintenance:**
1. `/codeguide-generate` — create missing docs
2. `/codeguide-maintain` — fix stale/broken docs

**On commit (via mill-commit):**
1. `/codeguide-update` (auto-scoped to git diff)

**After working without mill-commit:**
1. `/codeguide-update 1h` (or `HEAD~3`, etc.)
