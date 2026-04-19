# Mill Overview

Top-level reference for the mill plugin's autonomous task flow. Read this first if you are new to mill, or returning to it after a while. The detailed schemas live under `doc/formats/`, `doc/prompts/`, and `doc/architecture/`; this document explains how they fit together (see the module table below for exact paths).

This file is discoverable via grep / search across `plugins/mill/`. A `README.md` link is a future enhancement.

## Two-Thread Architecture

Mill executes a task across two threads with a hard handoff at plan approval:

```
                   Thread A                    Thread B
                   (designer)                  (implementer-orchestrator)

   /mill-start  →  Phase 1: Discussion   ─┐
                                          │   (same conversation, same model: opus)
   /mill-go     →  Phase 2: Plan         ─┘
                   ─ plan written
                   ─ plan reviewed
                   ─ approved
                   │
                   │ spawn via millpy.entrypoints.spawn_agent
                   │ (Bash run_in_background: true + Monitor)
                   ▼
                                          ──→  Phase 3: Implement
                                               ─ test baseline
                                               ─ steps + commits + tests
                                               ─ code review (read-only)
                                               ─ apply review fixes
                                               │
                                          ──→  Phase 4: Merge
                                               ─ codeguide-update
                                               ─ post-review commit
                                               ─ mill-merge (if auto-merge: true)
                                               ─ exit JSON
                   │                           │
                   ◀───────────────────────────┘
                   blocked, polling status.md, finally:
                   read status.md authoritative phase
                   report to user
                   exit
```

**Thread A = designer.** Runs `mill-start` (Phase 1) and the plan-writing portion of `mill-go` (Phase 2). Defaults to opus because design decisions and plan structure benefit from deep reasoning. Thread A owns the discussion file, the plan file, and the plan-review fix loop. After spawning Thread B, Thread A blocks and does not modify any files except the status report it ultimately gives the user.

**Thread B = implementer-orchestrator.** Spawned by `mill-go` Phase: Spawn Thread B. Defaults to sonnet because implementing an atomic plan is more mechanical than designing one. Thread B owns the test baseline, all step implementations and commits, the code-review fix loop, codeguide-update, and the merge.

**The hard invariant:** Thread A never resurrects after spawning Thread B. Once the plan is approved and Thread B starts, Thread A's responsibilities are: block, monitor, report. No late fix work. No re-entering Phase 2. This preserves the cost/context boundary at plan approval — Opus work ends, mid-range work begins, and the cheaper model is not dragged back into Opus context.

## Four-Phase Flow

| Phase | Skill | Thread | Model slot | Output artifacts |
|---|---|---|---|---|
| **1. Discussion** | `mill-start` | Thread A | `models.session` | `.millhouse/wiki/active/<slug>/discussion.md`, `status.md` `phase: discussed` |
| **2. Plan** | `mill-go` (Phase 2) | Thread A | `models.session` (writer), `models.plan-review.<N>` (reviewer) | `.millhouse/wiki/active/<slug>/plan/` (`approved: true`), `status.md` `phase: planned` |
| **3. Implement** | `mill-go` spawns Thread B via `millpy.entrypoints.spawn_agent` | Thread B | `models.implementer` (Thread B), `models.code-review.<N>` (reviewer) | All step commits, `status.md` `phase: testing/reviewing/complete` |
| **4. Merge** | Thread B invokes `mill-merge` skill | Thread B | `models.implementer` | Merge commit on parent, `status.md` `phase: complete`, `Home.md` `[done]` marker (set by `mill-merge`) |

Phases 1+2 share Thread A's conversation context. Phase 1 ends when the user types `/mill-go` in the same conversation; Phase 2 begins immediately in that thread. Phase 3 begins when Phase 2 spawns Thread B as a backgrounded subprocess.

## Spawn Mechanism

All sub-agent spawns in mill go through two Python entrypoints:

1. **Agent spawner — `millpy.entrypoints.spawn_agent`**: The single backend swap point for implementer and ad-hoc agent spawns. Invoked as `PYTHONPATH=<scripts-dir> python -m millpy.entrypoints.spawn_agent --role <role> --prompt-file <path> --provider <model>`. Supports `claude` (`opus`, `sonnet`, `haiku`) backends.

2. **Reviewer spawner — `millpy.entrypoints.spawn_reviewer`**: Resolves named reviewer recipes from config, gathers file scope for bulk reviews, spawns N parallel workers, routes through a handler model, and emits a single JSON line. Orchestrators call `spawn_reviewer`; it calls `spawn_agent` internally. See `plugins/mill/doc/architecture/reviewer-modules.md` for the full dispatch mode guide.

### Entrypoint signatures

**`spawn_agent`:**

```bash
PYTHONPATH=<scripts-dir> python -m millpy.entrypoints.spawn_agent \
  --role <reviewer|implementer> \
  --prompt-file <path-to-prompt> \
  --provider <model-name> \
  [--max-turns <int>] \
  [--work-dir <path>]
```

- `--role` — required. `reviewer` or `implementer`. Determines max-turns default and the JSON return shape contract validated on exit.
- `--prompt-file` — required. Path to a materialized prompt file. Callers materialize their prompt template (e.g. `discussion-review.md`, `plan-review.md`, `code-review.md`, `implementer-brief.md`) into a concrete file under `.millhouse/scratch/` and pass the path here.
- `--provider` — required. The model to invoke. `opus`, `sonnet`, `haiku` are routed to the `claude` backend. Unrecognized names exit with code 3.
- `--max-turns` — optional. Defaults by role: reviewer = 20, implementer = 200.
- `--work-dir` — optional. Defaults to cwd.

**`spawn_reviewer`:**

```bash
PYTHONPATH=<scripts-dir> python -m millpy.entrypoints.spawn_reviewer \
  --reviewer-name <name> \
  --prompt-file <path> \
  --phase <discussion|plan|code> \
  --round <N> \
  --plan-start-hash <sha>
```

### Synchronicity

Both entrypoints are **synchronous from their own perspective**. They invoke `claude -p --model <model> --max-turns <max> --output-format json`, wait for it to exit, parse the JSON output, validate the role-specific return shape, and write a single JSON line to stdout.

For long-running implementer runs, **the Bash tool handles backgrounding**. `mill-go` invokes `spawn_agent` via `Bash(run_in_background: true)` and monitors with the `Monitor` tool. Backgrounding lives at the harness layer, not the entrypoint layer.

### Return contract per role

- **Reviewer:** stdout is one JSON line `{"verdict": "APPROVE" | "REQUEST_CHANGES" | "GAPS_FOUND", "review_file": "<absolute-path>"}`. (Discussion review uses `GAPS_FOUND`; plan and code review use `REQUEST_CHANGES`. The entrypoint validates that the JSON has `verdict` and `review_file` keys.)
- **Implementer:** stdout is one JSON line `{"phase": "complete" | "blocked" | "pr-pending", "status_file": "<path>", "final_commit": "<sha-or-null>"}`. The entrypoint extracts this from the `result` field of `claude -p`'s JSON wrapper. Thread B writes the JSON as its final response text; the entrypoint mediates the pipe to its own stdout.

### Exit codes

- `0` — success, JSON line on stdout
- `1` — infrastructure error (claude backend failure, JSON parse error, missing prompt file, validation failure)
- `3` — not-implemented backend (`--provider` is not a recognized model name)

## Reviewer/Fixer Separation

The principle, stated as one rule: **The thread that produced the artifact fixes the artifact.** Reviewers are read-only. They evaluate, write a report, and return a verdict. They never modify the artifact under review.

| Artifact | Reviewer (cold, read-only) | Fixer |
|---|---|---|
| `discussion.md` | discussion-reviewer (`spawn_reviewer --phase discussion`) | `mill-start` (Thread A), with user consultation for gaps |
| `plan/` | plan-reviewer (`spawn_reviewer --phase plan`) | `mill-go` (Thread A), via `mill-receiving-review` skill |
| Code diff | code-reviewer (`spawn_reviewer --phase code`) | Thread B (the implementer-orchestrator), via `mill-receiving-review` skill |

This decouples reviewer model choice from fix capability. Reviewers can be swapped to cheap or non-Claude models later (a follow-up task) without losing fix quality, because the fixer is the thread that holds the freshest context for the artifact.

`mill-receiving-review` is the decision tree all fixers apply: VERIFY accuracy → HARM CHECK → FIX or PUSH BACK. It must be invoked **before** evaluating any reviewer finding. See `plugins/mill/skills/mill-receiving-review/SKILL.md`.

## Config Resolution

### `#config-resolution`

Orchestrator skills (`mill-go`, `mill-start`, Thread B) resolve a reviewer name from `review-modules.<phase>.<round>` in `.millhouse/config.yaml`, then pass that name to `spawn-reviewer.py --reviewer-name`. `spawn-reviewer.py` reads the matching `reviewers.<name>` recipe and dispatches accordingly.

For round `N`, the resolving skill looks up `review-modules.<phase>.<N>`. If that integer key is absent, it falls back to `review-modules.<phase>.default`. Rounds past the highest explicit index always use `default`. The `default` key is required for every phase slot.

YAML integer keys must be coerced to strings before lookup — keys are always compared as strings. `spawn-reviewer.py` performs this coercion internally. Orchestrator skills pass only `--reviewer-name <name>` and `--round <N>`; they do not read the recipe themselves.

Worked example:

```yaml
pipeline:
  plan-review:
    rounds: 3
    default: g3flash-x3-sonnetmax
    1: g3pro-x2-opus
  discussion-review:
    rounds: 2
    default: sonnetmax
```

- Plan round 1 → ensemble `g3pro-x2-opus` (2 Gemini Pro workers + Opus handler)
- Plan round 2, 3 → `g3flash-x3-sonnetmax` (falls through to `default`)
- Discussion all rounds → `sonnetmax` (single worker)

See `plugins/mill/doc/architecture/reviewer-modules.md` for the full registry schema and dispatch mode guide.

## Config Validation

### `#config-validation`

**Entry-time validation (fail-loud).** `mill-start` and `mill-go` validate the `pipeline:` block on entry. On failure, both skills stop with the exact error message:
   ```
   Config schema out of date. Expected reviewers: and review-modules: blocks. Run 'mill-setup' to auto-migrate.
   ```
   Validation runs every time, not just after migration. It catches edge cases the auto-migration cannot handle (e.g. a hand-edited config that introduces a malformed shape).

In-flight `.millhouse/wiki/active/<slug>/discussion.md` or `plan/` files written before this task landed are a clean break — single-user repo. Any mid-flow task must be re-run.

## Documentation Map

| Document | What it covers |
|---|---|
| `plugins/mill/doc/formats/discussion.md` | Schema for `.millhouse/wiki/active/<slug>/discussion.md` (mill-start's output) |
| `plugins/mill/doc/prompts/discussion-review.md` | Discussion-reviewer protocol (read-only sub-agent invoked by mill-start) |
| `plugins/mill/doc/formats/plan.md` | Schema for `.millhouse/wiki/active/<slug>/plan/`, including the atomic step-card invariant |
| `plugins/mill/doc/prompts/plan-review.md` | Plan-reviewer protocol (read-only sub-agent invoked by mill-go) |
| `plugins/mill/doc/prompts/code-review.md` | Code-reviewer protocol (`tool-use` dispatch — Claude reviewers) |
| `plugins/mill/doc/prompts/code-review-bulk.md` | Code-reviewer prompt template for `bulk` dispatch (Gemini workers) |
| `plugins/mill/doc/architecture/reviewer-modules.md` | Reviewer-module architecture guide: recipe schema, dispatch modes, failure modes, adding ensembles |
| `plugins/mill/doc/prompts/implementer-brief.md` | Thread B's prompt template — the runtime spec for Phase 3+4 |
| `plugins/mill/doc/formats/handoff-brief.md` | Deprecated — handoff briefs are no longer used |
| `plugins/mill/doc/formats/tasksmd.md` | `Home.md` format reference (the wiki-based task list) |
| `plugins/mill/doc/formats/validation.md` | Structural validation rules for `Home.md`, `status.md`, `config.yaml`, and `plan/` |
| `plugins/mill/doc/formats/markdown.md` | Markdown formatting conventions for mill-generated files |

## Task System — Wiki-Based Layout

Per-task runtime state lives in the GitHub Wiki (`<repo>.wiki.git`), cloned locally at `<worktree-parent>/<repo>.wiki/`. Each worktree accesses the wiki via a `.millhouse/wiki/` junction at its root:

```
.millhouse/wiki/                ← junction → <worktree-parent>/<repo>.wiki/
  Home.md                       ← task list (shared; read/write via tasks_md)
  _Sidebar.md                   ← generated wiki sidebar
  active/
    <slug>/
      status.md                 ← per-task phase tracking (IPC channel)
      discussion.md             ← mill-start output
      plan/                     ← mill-plan output (v3 flat-card layout)
      reviews/                  ← reviewer reports and fixer reports
```

The wiki is the source of truth for task state across machines. Every orchestrator entry point calls `millpy.tasks.wiki.sync_pull(cfg)` before reading wiki state. Every wiki write uses `wiki.write_commit_push` (for shared files like `Home.md`) or direct path writes followed by `wiki.write_commit_push` (for per-task files).

The `.millhouse/wiki/` junction is gitignored and NOT committed to the main repo. `mill-setup` creates it. `mill-resume` recreates it on a new machine.

## Status File Channel

`.millhouse/wiki/active/<slug>/status.md` is the only IPC channel between Thread A and Thread B. Thread B writes per-step updates to status.md after every phase transition, every step boundary, and every retry. Thread A reads status.md via `Monitor` (which streams the background subprocess's output) and a final read after the background process exits.

Status.md writes go exclusively through `millpy.tasks.status_md.append_phase(path, phase, cfg=cfg)`. Free-form editing of status.md is banned — use `append_phase`.

User visibility relies on VS Code live-updating the status.md file in the editor. There is no socket, no queue, no fancy IPC. The status file is the truth — if its `phase:` value disagrees with the script's exit JSON, mill-go trusts status.md and reports the discrepancy.

Format details and the timeline text-block schema live in `plugins/mill/doc/formats/discussion.md` (`## status.md Schema` section).
