# Mill Overview

Top-level reference for the mill plugin's autonomous task flow. Read this first if you are new to mill, or returning to it after a while. The detailed schemas live in `doc/modules/`; this document explains how they fit together.

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
                   │ spawn via spawn-agent.ps1
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
| **1. Discussion** | `mill-start` | Thread A | `models.session` | `_millhouse/task/discussion.md`, `status.md` `phase: discussed` |
| **2. Plan** | `mill-go` (Phase 2) | Thread A | `models.session` (writer), `models.plan-review.<N>` (reviewer) | `_millhouse/task/plan.md` (`approved: true`), `status.md` `phase: planned` |
| **3. Implement** | `mill-go` spawns Thread B via `spawn-agent.ps1 -Role implementer` | Thread B | `models.implementer` (Thread B), `models.code-review.<N>` (reviewer) | All step commits, `status.md` `phase: testing/reviewing/complete` |
| **4. Merge** | Thread B invokes `mill-merge` skill | Thread B | `models.implementer` | Merge commit on parent, `status.md` `phase: complete`, `tasks.md` `[done]` marker (set by `mill-merge`) |

Phases 1+2 share Thread A's conversation context. Phase 1 ends when the user types `/mill-go` in the same conversation; Phase 2 begins immediately in that thread. Phase 3 begins when Phase 2 spawns Thread B as a backgrounded subprocess.

## Spawn Mechanism

All sub-agent spawns in mill go through `plugins/mill/scripts/spawn-agent.ps1`. This is the swap-backend integration point: today only the `claude` backend is wired, but the script structure makes adding `ollama`, `gemini-cli`, etc. straightforward in a follow-up task.

### Script signature

```
spawn-agent.ps1 -Role <reviewer|implementer>
                -PromptFile <path-to-prompt>
                -ProviderName <model-name>
                [-MaxTurns <int>]
                [-WorkDir <path>]
```

- `-Role` — required. `reviewer` or `implementer`. Determines max-turns default and the JSON return shape contract the script validates against.
- `-PromptFile` — required. Path to a materialized prompt file. Callers materialize their prompt template (e.g. `discussion-review.md`, `plan-review.md`, `code-review.md`, `implementer-brief.md`) into a concrete file under `_millhouse/scratch/` and pass the path here.
- `-ProviderName` — required. The model to invoke. In this task: `opus`, `sonnet`, `haiku` are routed to the `claude` backend. Other names (`ollama-*`, `gemini-*`, `qwen*`, `vllm*`, anything else) exit with code 3 and the message "[spawn-agent] Provider '<name>' not implemented in this task. See plugins/mill/doc/overview.md#config-migration for follow-up."
- `-MaxTurns` — optional. Defaults by role: reviewer = 20, implementer = 200. Override only when a specific run needs a different cap.
- `-WorkDir` — optional. Defaults to `$PWD`.

### Synchronicity

The script is **synchronous from its own perspective**. It pipes the prompt file via stdin to `claude -p --model <model> --max-turns <max> --output-format json`, waits for it to exit, parses the JSON output, validates the role-specific return shape, and writes a single JSON line to its own stdout.

For long-running implementer runs, **the Bash tool handles backgrounding**. `mill-go` invokes the script via `Bash(run_in_background: true)` and monitors the resulting background shell with the `Monitor` tool. The script does **not** detach itself with `Start-Process` or `Start-Job`. Backgrounding lives at the harness layer, not the script layer.

### Return contract per role

- **Reviewer:** stdout is one JSON line `{"verdict": "APPROVE" | "REQUEST_CHANGES" | "GAPS_FOUND", "review_file": "<absolute-path>"}`. (Discussion review uses `GAPS_FOUND`; plan and code review use `REQUEST_CHANGES`. The script does not enforce which verdict word — that is the prompt template's responsibility. The script only validates that the JSON has `verdict` and `review_file` keys.)
- **Implementer:** stdout is one JSON line `{"phase": "complete" | "blocked" | "pr-pending", "status_file": "<path>", "final_commit": "<sha-or-null>"}`. The script extracts this from the `result` field of `claude -p`'s JSON wrapper. Thread B writes the JSON as its final response text; the script mediates the pipe to its own stdout. Thread B does not write to the script's stdout directly.

### Exit codes

- `0` — success, JSON line on stdout
- `1` — infrastructure error (claude backend failure, JSON parse error, missing prompt file, validation failure)
- `3` — not-implemented backend (`-ProviderName` is not a recognized Claude model name in this task)

There is no exit code 2 (the historical 0d15316 script used 2 for "fallback to Agent tool"; that fallback is removed because this script is the unified spawn point).

## Reviewer/Fixer Separation

The principle, stated as one rule: **The thread that produced the artifact fixes the artifact.** Reviewers are read-only. They evaluate, write a report, and return a verdict. They never modify the artifact under review.

| Artifact | Reviewer (cold, read-only) | Fixer |
|---|---|---|
| `discussion.md` | discussion-reviewer (`spawn-agent.ps1 -Role reviewer`) | `mill-start` (Thread A), with user consultation for gaps |
| `plan.md` | plan-reviewer (`spawn-agent.ps1 -Role reviewer`) | `mill-go` (Thread A), via `mill-receiving-review` skill |
| Code diff | code-reviewer (`spawn-agent.ps1 -Role reviewer`) | Thread B (the implementer-orchestrator), via `mill-receiving-review` skill |

This decouples reviewer model choice from fix capability. Reviewers can be swapped to cheap or non-Claude models later (a follow-up task) without losing fix quality, because the fixer is the thread that holds the freshest context for the artifact.

`mill-receiving-review` is the decision tree all fixers apply: VERIFY accuracy → HARM CHECK → FIX or PUSH BACK. It must be invoked **before** evaluating any reviewer finding. See `plugins/mill/skills/mill-receiving-review/SKILL.md`.

## Config Resolution

### `#config-resolution`

For review round `N`, the resolving skill looks up `models.<review-type>.<N>`. If that integer key is absent, it falls back to `models.<review-type>.default`. Rounds past the highest explicit index always use `default`. The `default` key is required for every review slot.

YAML integer keys must be coerced to strings before lookup — keys are always compared as strings. The resolution helper in mill-go and mill-start performs the coercion. `spawn-agent.ps1` does **not** read config; the orchestrator skills resolve the model name and pass it as `-ProviderName`.

Worked example:

```yaml
models:
  plan-review:
    1: opus
    2: sonnet
    default: sonnet
```

- Round 1 → `opus`
- Round 2 → `sonnet`
- Round 3, 4, 5, ... → `sonnet` (falls through to `default`)

If a slot has only `default`:

```yaml
models:
  code-review:
    default: sonnet
```

- All rounds → `sonnet`

The schema accepts provider names instead of Claude model names in a future `llm-providers:` block, without further schema changes.

## Config Migration

### `#config-migration`

Two layers protect existing installs from the schema change introduced in this task:

1. **`mill-setup` auto-migration (Layer 1, automatic).** When `_millhouse/config.yaml` already exists, `mill-setup` Step 4b reads the existing `models:` block and updates it in place:
   - For required scalar keys (`session`, `implementer`, `explore`): if missing, append with the default value.
   - For per-round object keys (`discussion-review`, `plan-review`, `code-review`):
     - Absent → insert as `<key>:\n    default: <default-value>` (`discussion-review` → `opus`; the rest → `sonnet`).
     - Scalar (e.g. `plan-review: sonnet`) → rewrite to `<key>:\n    default: <existing-scalar-value>`. The user's choice is preserved as the new `default`.
     - Object with `default` sub-key → leave alone (idempotent).
     - Object missing `default` → insert `default: <hardcoded-default>` under it.
   - Print a diff of what changed. Write the updated file. No git commit (`_millhouse/` is gitignored).
   - Auto-migration runs every time `mill-setup` is invoked, so re-running it on a conformant config is a no-op.

2. **Entry-time validation (Layer 2, fail-loud).** `mill-start` and `mill-go` validate the `models:` block on entry per the rules in `validation.md` `## _millhouse/config.yaml`. On failure, both skills stop with the exact error message:
   ```
   Config schema out of date. Expected models.<slot> (<type>). Run 'mill-setup' to auto-migrate.
   ```
   Validation runs every time, not just after migration. It catches edge cases the auto-migration cannot handle (e.g. a hand-edited config that introduces a malformed shape).

In-flight `_millhouse/task/discussion.md` or `plan.md` files written before this task landed are a clean break — single-user repo. Any mid-flow task must be re-run.

## Documentation Map

| Document | What it covers |
|---|---|
| `doc/modules/discussion-format.md` | Schema for `_millhouse/task/discussion.md` (mill-start's output) |
| `doc/modules/discussion-review.md` | Discussion-reviewer protocol (read-only sub-agent invoked by mill-start) |
| `doc/modules/plan-format.md` | Schema for `_millhouse/task/plan.md`, including the atomic step-card invariant |
| `doc/modules/plan-review.md` | Plan-reviewer protocol (read-only sub-agent invoked by mill-go) |
| `doc/modules/code-review.md` | Code-reviewer protocol (read-only sub-agent invoked by Thread B) |
| `doc/modules/implementer-brief.md` | Thread B's prompt template — the runtime spec for Phase 3+4 |
| `doc/modules/handoff-brief.md` | `_millhouse/handoff.md` format (mill-spawn → mill-start handoff) |
| `doc/modules/tasksmd-format.md` | `tasks.md` format reference (the git-tracked task list) |
| `doc/modules/validation.md` | Structural validation rules for `tasks.md`, `status.md`, `config.yaml`, and `plan.md` |
| `doc/modules/markdown-format.md` | Markdown formatting conventions for mill-generated files |

## Status File Channel

`_millhouse/task/status.md` is the only IPC channel between Thread A and Thread B. Thread B writes per-step updates to status.md after every phase transition, every step boundary, and every retry. Thread A reads status.md via `Monitor` (which streams the background subprocess's output) and a final read after the background process exits.

User visibility relies on VS Code live-updating the status.md file in the editor. There is no socket, no queue, no fancy IPC. The status file is the truth — if its `phase:` value disagrees with the script's exit JSON, mill-go trusts status.md and reports the discrepancy.

Format details and the timeline text-block schema live in `doc/modules/discussion-format.md` (`## status.md Schema` section).
