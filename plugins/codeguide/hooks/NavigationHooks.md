# Navigation Enforcement Hooks

Documents the hook system that enforces correct `_codeguide/` routing and catches navigation failures for guide improvement.

---

## Two Rules Being Enforced

### Rule 1 — Route first

Before opening any source file or running any search, read the relevant project's `_codeguide/Overview.md`. This identifies which files are relevant without requiring pattern matching across the codebase.

### Rule 2 — Source files are the final step

`_codeguide/` docs route to the right files. They do not replace reading those files. For any factual question about behavior, logic, contracts, or values, the answer must come from the source — not from the doc. Docs may be incomplete or imprecise.

---

## Hook Inventory

Hooks are split into three layers: **base** (always active), **enforcement** (search blocking), and **audit** (parity tracking for review). Two flags in `_codeguide/config.yaml` control which layers are active:

- `enforcement` — adds session tracking and search blocking hooks. When on, search tools are blocked until Overview is read.
- `violation_logging` — adds subagent parity tracking hooks and enables violation logging to `runtime/navigation-issues.md`.

Toggle with `/codeguide-tracking enforcement on|off` or `/codeguide-tracking logging on|off`. The active hooks.json is rebuilt from composable base files (`hooks-base.json`, `hooks-enforcement.json`, `hooks-violation-logging.json`) by the merge script `_merge_hooks.py`.

### Shared modules

| File | What it does |
|---|---|
| `../scripts/_resolve.py` | Two-tier path resolution shared by all hooks and skills. Routing files (Overview.md, modules/) resolve from cwd. Metadata files (config.yaml, local-rules.md) resolve by walking up to the nearest ancestor that contains them. Also callable as a CLI: prints the metadata `_codeguide/` path. |
| `_merge_hooks.py` | Composes hooks.json from base files. Called by `/codeguide-tracking` when flags change. |

### Base hooks (`base_`)

Always active regardless of flags.

| Hook | Event | What it does |
|---|---|---|
| `base_inject_routing.py` | UserPromptSubmit, SubagentStart | Injects imperative routing instructions — Claude must actively Read Overview.md |

### Enforcement hooks (`enforce_`)

Active when `enforcement: true`. Create session state, enforce the "read Overview first" rule, and clean up.

| Hook | Event | What it does |
|---|---|---|
| `enforce_init_session.py` | UserPromptSubmit | Creates a turn-scoped session state file capturing the user prompt |
| `enforce_track_read.py` | PreToolUse (Read) | Sets `overview_read` flag when any `_codeguide/` file is accessed |
| `enforce_track_search.py` | PreToolUse (Grep/Glob/Bash) | Counts search calls; blocks after threshold if Overview not yet read; logs violations if `violation_logging: true` |
| `enforce_stop.py` | Stop | Logs parity issues if `violation_logging: true`; deletes the session state file |

### Audit hooks (`audit_`)

Active when `violation_logging: true`. Track subagent parity for `/review-navigation`.

| Hook | Event | What it does |
|---|---|---|
| `audit_track_task.py` | PreToolUse (Agent) | Counts subagent spawns for parity checking |
| `audit_track_subagent.py` | SubagentStart | Counts subagent injections for parity checking |

---

## How Enforcement Works

A turn-scoped session state file tracks whether `_codeguide/` has been read and how many search calls have been made. If the search count exceeds the threshold without `_codeguide/` having been read, the search tool is blocked until the guide is read.

All hooks use two-tier path resolution (`scripts/_resolve.py`): routing files (Overview.md, modules/) are resolved from cwd, while metadata files (config.yaml, local-rules.md) are found by walking up from cwd to the nearest ancestor containing them. This allows VS Code to open a subfolder while hooks still find repo-level configuration.

Subagents receive routing instructions (not the verbatim Overview) since they cannot inherit hook context. They must actively Read the Overview like the main conversation.

Violations are logged to `_codeguide/runtime/navigation-issues.md` with the user's prompt, for later review via `/review-navigation`.

---

## Language Configuration

`_codeguide/config.yaml` defines which file extensions are recognized as source files. Hooks read this at runtime — to support a new language, add its extension to the list.

---

## Runtime Directory

```
_codeguide/
└── runtime/                        ← not version-controlled
    ├── sessions/
    │   └── {session_id}-state.json ← turn-scoped, deleted on Stop
    └── navigation-issues.md        ← accumulated violation log
```

---

## Known Limitations

Doc maintenance is handled by skills, not hooks. Use `/codeguide-update` after making changes, or let mill-commit call it automatically. For larger updates, use `/codeguide-maintain` (scoped) or `/codeguide-generate` (scoped).

---

## Adjusting the Threshold

The search threshold is set in `enforce_track_search.py`. Start conservative and raise if legitimate work is being blocked.
