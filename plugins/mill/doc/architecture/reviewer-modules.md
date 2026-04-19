# Reviewer Modules

This document describes the two-level Python registry that backs `millpy`'s reviewer pipeline. Target audience: anyone adding a new reviewer, changing dispatch modes, or debugging reviewer behavior.

## Overview

The reviewer pipeline uses two registries defined in `millpy/reviewers/`:

- **`WORKERS`** (`reviewers/workers.py`) — named atomic worker configurations. Each entry is a `Worker` dataclass with a provider, model, dispatch mode, and optional effort level. Workers are the leaf nodes of the system.
- **`REVIEWERS`** (`reviewers/definitions.py`) — named ensemble compositions. Each entry is an `Ensemble` dataclass referencing workers by name. Single-worker reviews do not live in `REVIEWERS`; the engine auto-wraps a bare `WORKERS` name as a `SingleWorker` reviewer.

The abstraction boundary: `spawn-reviewer.py` (and `millpy.entrypoints.spawn_reviewer`) always emit one JSON line — `{"verdict": "APPROVE|REQUEST_CHANGES", "review_file": "<path>"}`. Orchestrators parse this line and proceed.

## WORKERS

`WORKERS: dict[str, Worker]` holds atomic (provider, model, effort, dispatch_mode) configurations.

`Worker` dataclass fields:

| Field | Type | Default | Description |
|---|---|---|---|
| `provider` | `str` | required | Backend provider: `claude`, `gemini`, or `ollama` |
| `model` | `str` | required | Model identifier string passed to the backend |
| `effort` | `str \| None` | `None` | Claude effort level (`max`). Non-None only for `claude` provider. |
| `dispatch_mode` | `str` | provider default | `tool-use` or `bulk`. Default: `claude`→`tool-use`, `ollama`→`tool-use`, `gemini`→`bulk`. |
| `max_turns` | `int` | `30` | Tool-use turn budget (ignored for bulk workers). |
| `extras` | `Mapping[str, object]` | `{}` | Provider-specific extras, e.g. `{"think": True}` for Ollama qwen3. |

`WORKERS` entries (Haiku omitted — insufficient for reviews):

| Name | Provider | Model | Effort | Dispatch |
|---|---|---|---|---|
| `sonnet` | claude | sonnet | — | tool-use |
| `sonnetmax` | claude | sonnet | max | tool-use |
| `opus` | claude | opus | — | tool-use |
| `opusmax` | claude | opus | max | tool-use |
| `g3flash` | gemini | gemini-3-flash-preview | — | bulk |
| `g3pro` | gemini | gemini-3-pro-preview | — | bulk |
| `glmflash` | ollama | glm-4.7-flash:latest | — | tool-use |
| `qwenthinker` | ollama | qwen3:30b-thinking | — | tool-use |

## REVIEWERS

`REVIEWERS: dict[str, Ensemble]` holds ensemble compositions referencing workers by name.

Naming convention: `<worker>-x<count>-<handler>` (e.g. `g3flash-x3-sonnetmax`).

`Ensemble` dataclass fields:

| Field | Type | Default | Description |
|---|---|---|---|
| `worker` | `str` | required | WORKERS key identifying the parallel worker |
| `worker_count` | `int` | required | Number of parallel workers to spawn (≥1) |
| `handler` | `str` | required | WORKERS key identifying the handler that synthesizes worker output |
| `handler_prep` | `bool` | `False` | When `True` and handler is tool-use, spawn a prep pass in parallel with workers (see `plugins/mill/doc/prompts/handler-prep.md`) |

`REVIEWERS` entries:

| Name | Worker | Count | Handler |
|---|---|---|---|
| `g3pro-x2-opus` | g3pro | 2 | opus |
| `g3flash-x3-sonnetmax` | g3flash | 3 | sonnetmax |
| `g3pro-x2-g3flash` | g3pro | 2 | g3flash |
| `g3flash-x3-g3flash` | g3flash | 3 | g3flash |

## Engine resolution

Resolution order in `millpy.reviewers.engine.run_reviewer`:

1. Check `REVIEWERS[reviewer_name]` — if found, wrap in `EnsembleReviewer` and dispatch.
2. Check `WORKERS[reviewer_name]` — if found, wrap in `SingleWorker` and dispatch.
3. Else raise `ConfigError(f"unknown reviewer: {reviewer_name}")`.

**Discussion-phase bulk guard:** If the resolved reviewer uses a bulk-mode worker and `phase == "discussion"`, the engine raises `ConfigError` before spawning anything. No `discussion-review-bulk.md` template exists; bulk is only defined for `plan` and `code` phases.

**Validate-before-mkdir (Fix E):** Reviewer name validation and the discussion-bulk guard run before any directory creation. A bad reviewer name does not create `.millhouse/scratch/reviews/`.

## Import-time validation

`millpy/reviewers/__init__.py` runs these checks at import time and raises `ValueError` immediately on any violation:

1. Every `Worker.provider` must be a key in `millpy.backends.BACKENDS` (`claude`, `gemini`, `ollama`).
2. `Worker.effort` must be `None` unless `provider == "claude"`.
3. Every `Worker.dispatch_mode` is `tool-use` or `bulk`.
4. Every `Ensemble.worker` and `Ensemble.handler` must be valid `WORKERS` keys.
5. Every `Ensemble.worker_count >= 1`.
6. Name-space non-overlap: no name appears in both `WORKERS` and `REVIEWERS`.

These invariants are also accessible via `millpy.reviewers.validate_registries()`.

## Config integration

`.millhouse/config.yaml` uses the `pipeline:` block to name reviewers by phase:

```yaml
pipeline:
  discussion-review:
    rounds: 2
    default: sonnetmax
  plan-review:
    rounds: 3
    default: g3flash-x3-sonnetmax
    holistic: sonnetmax        # v3: holistic reviewer (tool-use, sees whole plan dir)
    per-card: g3flash          # v3: per-card reviewer (bulk, sees one card + reads files)
  code-review:
    rounds: 3
    default: g3flash-x3-sonnetmax
```

Each value (`sonnetmax`, `g3flash-x3-sonnetmax`) is either a `WORKERS` key or a `REVIEWERS` key. The engine treats both syntactically identically — the registry lookup determines the actual dispatch shape.

### Holistic and per-card keys (v3)

Under `plan-review:`, two optional keys select reviewers for v3 card-based fan-out:

| Key | Slice type | Reviewer type | Description |
|---|---|---|---|
| `holistic` | `"holistic"` | tool-use | Sees the whole plan directory; checks cross-card consistency |
| `per-card` | `"per-card"` | bulk | Sees one card + inlined `reads:` files; checks atomicity and completeness |

When absent, resolution falls back to `default`.

### Per-round overrides

Per-round overrides use the round number as key (v2 path; ignored when `slice_type` is set):

```yaml
pipeline:
  plan-review:
    rounds: 3
    default: g3flash-x3-sonnetmax
    2: opusmax
```

### resolve_reviewer_name

`millpy.core.config.resolve_reviewer_name(cfg, phase, round, slice_type=None)` implements all lookup paths:

- **`slice_type` provided** (e.g. `"holistic"`, `"per-card"`): try `pipeline.<phase>-review.<slice_type>` first, then `pipeline.<phase>-review.default`.
- **`slice_type` is None** (backward-compatible): try `pipeline.<phase>-review.<round>` first, then `pipeline.<phase>-review.default`.

### v3 card-based fan-out worked example

For a v3 plan with cards `[1, 2, 3]` and config:
```yaml
pipeline:
  plan-review:
    holistic: sonnetmax
    per-card: g3flash
```

The orchestrator:
1. Calls `PlanReviewLoop(PlanOverviewV3(card_numbers=[1, 2, 3]), max_rounds=3).next_round_plan()` → `["card-1", "card-2", "card-3", "holistic"]`.
2. For each `card-N` slice: spawns `spawn_reviewer --slice-type per-card` → resolves `g3flash` (bulk), inlines card file + reads files via `<FILES_PAYLOAD>`.
3. For `holistic` slice: spawns `spawn_reviewer --slice-type holistic` → resolves `sonnetmax` (tool-use), passes `--plan-dir-path`.
4. Collects all verdicts → calls `record_round_result()` → determines `APPROVED`, `CONTINUE`, `BLOCKED_NON_PROGRESS`, or `BLOCKED_MAX_ROUNDS`.

## Adding a new worker or ensemble

To add a new atomic worker, add one entry to `WORKERS` in `millpy/reviewers/workers.py`. To add a new ensemble, add one entry to `REVIEWERS` in `millpy/reviewers/definitions.py`. Import-time validation will catch any reference errors at the next `import millpy.reviewers`.
