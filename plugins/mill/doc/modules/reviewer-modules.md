# Reviewer-Module Abstraction Guide

This guide explains the two-layer reviewer architecture introduced by the Gemini CLI + ensemble reviewer task. Target audience: anyone adding a new reviewer recipe, changing dispatch modes, or debugging reviewer behavior.

## 1. Overview

The reviewer pipeline has two layers:

**Model layer — `plugins/mill/scripts/spawn-agent.ps1`**

Single entry point for all LLM invocations. Accepts `-Role reviewer -ProviderName <model> -DispatchMode tool-use|bulk`. Supports Claude (`opus`, `sonnet`, `haiku`) and Gemini (`gemini-3-pro`, `gemini-flash`) backends. All orchestrators call this script; it is the single swap point for new backends.

**Reviewer-module layer — `plugins/mill/scripts/spawn-reviewer.py`**

Resolves a named reviewer recipe from `_millhouse/config.yaml`, gathers file scope for bulk reviews, spawns N workers in parallel (for ensemble recipes), routes results through a handler, and emits the standard JSON line. Callers (`mill-go`, `mill-start`, Thread B) never see whether they invoked a single reviewer or an N-worker ensemble — the output contract is byte-identical.

The clean abstraction boundary: `spawn-reviewer.py` stdout is always `{"verdict": "APPROVE|REQUEST_CHANGES", "review_file": "<path>"}`. Orchestrators parse this one line and proceed.

## 2. Recipe Schema

Each entry under `reviewers:` in `_millhouse/config.yaml` is a recipe object:

| Field | Type | Required | Description |
|---|---|---|---|
| `worker-model` | string | required | Provider name (`opus`, `sonnet`, `haiku`, `gemini-3-pro`, `gemini-flash`) |
| `worker-count` | int ≥ 1 | required | Number of parallel workers to spawn |
| `dispatch` | `tool-use` \| `bulk` | required | Dispatch mode (see Section 5) |
| `prompt-template` | string (repo-relative) | required when `dispatch=bulk` | Bulk prompt template path |
| `handler-model` | string | required when `dispatch=bulk` and `worker-count>=2` | Handler model name |
| `max-bundle-chars` | int | optional | Max prompt size in chars; default 200000 for bulk |
| `fallback` | string (reviewer name) | optional | Fallback recipe on bot-gate; single-hop only |

See `plugins/mill/doc/modules/validation.md` for the full schema validation rules.

## 3. Adding a New Reviewer

Suppose you want a cheap `single-haiku` reviewer for discussion-review to save API cost:

**Step 1:** Add the recipe under `reviewers:` in `_millhouse/config.yaml`:

```yaml
reviewers:
  single-haiku:
    worker-model: haiku
    worker-count: 1
    dispatch: tool-use
```

**Step 2:** Wire it into the phase mapping under `review-modules:`:

```yaml
review-modules:
  discussion:
    default: single-haiku    # was: single-opus
```

**Diff:**

```yaml
reviewers:
+  single-haiku:
+    worker-model: haiku
+    worker-count: 1
+    dispatch: tool-use

review-modules:
  discussion:
-    default: single-opus
+    default: single-haiku
```

No code changes required.

## 4. Adding an Ensemble Reviewer

A hypothetical 4-worker Sonnet ensemble with a Sonnet handler:

```yaml
reviewers:
  ensemble-sonnet4:
    worker-model: sonnet
    worker-count: 4
    dispatch: bulk
    handler-model: sonnet
    prompt-template: plugins/mill/doc/modules/code-review-bulk.md
    max-bundle-chars: 150000
    fallback: single-opus
```

Wire it as the code-review default for rounds 1-2, falling back to the existing ensemble on round 3:

```yaml
review-modules:
  code:
    1: ensemble-sonnet4
    2: ensemble-sonnet4
    default: ensemble-gemini3-opus
```

**Diff against baseline config:**

```yaml
reviewers:
+  ensemble-sonnet4:
+    worker-model: sonnet
+    worker-count: 4
+    dispatch: bulk
+    handler-model: sonnet
+    prompt-template: plugins/mill/doc/modules/code-review-bulk.md
+    max-bundle-chars: 150000
+    fallback: single-opus

review-modules:
  code:
-    default: ensemble-gemini3-opus
+    1: ensemble-sonnet4
+    2: ensemble-sonnet4
+    default: ensemble-gemini3-opus
```

## 5. Dispatch Mode Choice

**Use `tool-use` when:**
- The reviewer is a Claude model (Opus, Sonnet, Haiku).
- No rate-limit concern — Claude's API allows many requests per minute.
- The existing tool-use prompt templates are already written for this model.
- Single-worker recipes (`worker-count: 1`) — degenerate ensembles where no handler is needed.

**Use `bulk` when:**
- The reviewer is a Gemini CLI model.
- The Code Assist for Individuals tier limits to ~5 req/min, making per-tool-call requests unworkable.
- `worker-count >= 2` (multi-worker ensemble) — always requires `bulk` because tool-use multi-worker is explicitly forbidden.

**Why discussion-review can never be bulk:**
There is no deterministic file scope for discussion-review — the discussion is a free-form document with no `## Files` section. The engine raises `ConfigError("discussion-review cannot use bulk dispatch — no deterministic file scope")` if you try. Use `tool-use` for discussion-review at all times.

## 6. Failure Modes and Fallback

Worker failures are classified by `spawn-agent.ps1` exit code:

| Exit code | Kind | Description |
|---|---|---|
| 10 | `rate_limit` | Gemini 429 / RESOURCE_EXHAUSTED |
| 11 | `bot_gate` | Google OAuth anti-bot detection tripped |
| 12 | `binary_missing` | `C:\Code\tools\bin\gemini.cmd` not found |
| 13 | `exit_nonzero` | Unclassified non-zero exit |
| 1 | `malformed` | Worker output not parseable |

**Degradation:** A failed worker is dropped (no retry). The ensemble degrades to N-1. If successes < 2 for a `worker-count >= 2` recipe → `fatal: degraded-fatal` → `spawn-reviewer.py` exits non-zero.

**Bot-gate session marker:** When any `WorkerFailure.kind == 'bot_gate'` is detected, `spawn-reviewer.py` writes `_millhouse/scratch/reviews/bot-gated-<recipe-name>.flag`. Subsequent invocations in the same session detect this marker on startup and skip the primary recipe, using `recipe.fallback` directly without re-probing the gated detector. The marker is cleared on `mill-setup` or manual cleanup of `_millhouse/scratch/`.

**Fallback:** single-hop only. If the fallback recipe also fails, the engine exits with a clear error naming both recipes.

See `plugins/mill/scripts/spawn_reviewer.py` Steps 6 and 7 for the implementation.

## 7. Verifying a New Recipe

To smoke-test a new recipe without running a full mill task:

```bash
# From the repo root
python plugins/mill/scripts/spawn-reviewer.py \
  --reviewer-name <your-recipe-name> \
  --prompt-file _millhouse/scratch/plan-review-prompt-r1.md \
  --phase plan \
  --round 1
```

Expected output on success: a single JSON line `{"verdict": "APPROVE|REQUEST_CHANGES", "review_file": "..."}` on stdout.

Check stderr for `[spawn-reviewer]` log lines that show the resolved recipe and any degradation notes.

For bulk recipes (code-review phase), also pass `--plan-start-hash <hash>` so the engine can compute file scope:

```bash
python plugins/mill/scripts/spawn-reviewer.py \
  --reviewer-name ensemble-gemini3-opus \
  --prompt-file _millhouse/scratch/code-review-prompt-r1.md \
  --phase code \
  --round 1 \
  --plan-start-hash $(git log --oneline -10 | tail -1 | cut -d' ' -f1)
```

## Cross-References

- `plugins/mill/scripts/spawn_reviewer.py` — canonical source for dispatch behavior
- `plugins/mill/scripts/spawn-agent.ps1` — model layer entry point
- `plugins/mill/doc/modules/code-review.md` — tool-use reviewer prompt template
- `plugins/mill/doc/modules/code-review-bulk.md` — bulk reviewer prompt template
- `plugins/mill/doc/modules/validation.md` — config schema rules for `reviewers:` and `review-modules:`
- `plugins/mill/doc/overview.md` — round-resolution rule and architecture overview
- `plugins/mill/skills/review-handler/SKILL.md` — handler prompt for ensemble synthesis
