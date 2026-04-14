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

Initial `WORKERS` entries (Haiku omitted — judged insufficient for reviews):

| Name | Provider | Model | Effort | Dispatch |
|---|---|---|---|---|
| `sonnet` | claude | sonnet | — | tool-use |
| `sonnetmax` | claude | sonnet | max | tool-use |
| `opus` | claude | opus | — | tool-use |
| `opusmax` | claude | opus | max | tool-use |
| `gemini3flash` | gemini | gemini-3-flash-preview | — | bulk |
| `gemini3pro` | gemini | gemini-3-pro-preview | — | bulk |
| `glmflash` | ollama | glm-4.7-flash:latest | — | tool-use |
| `qwenthinker` | ollama | qwen3:30b-thinking | — | tool-use |

## REVIEWERS

`REVIEWERS: dict[str, Ensemble]` holds ensemble compositions referencing workers by name.

`Ensemble` dataclass fields:

| Field | Type | Default | Description |
|---|---|---|---|
| `worker` | `str` | required | WORKERS key identifying the parallel worker |
| `worker_count` | `int` | required | Number of parallel workers to spawn (≥1) |
| `handler` | `str` | required | WORKERS key identifying the handler that synthesizes worker output |
| `handler_prep` | `bool` | `False` | When `True` and handler is tool-use, spawn a prep pass in parallel with workers (see `plugins/mill/doc/prompts/handler-prep.md`) |

Initial `REVIEWERS` entries:

| Name | Worker | Count | Handler |
|---|---|---|---|
| `ensemble-gemini3pro-x2-opus` | gemini3pro | 2 | opus |
| `ensemble-gemini3flash-x3-sonnetmax` | gemini3flash | 3 | sonnetmax |
| `ensemble-gemini3pro-x2-gemini3flash` | gemini3pro | 2 | gemini3flash |

## Engine resolution

Resolution order in `millpy.reviewers.engine.run_reviewer`:

1. Check `REVIEWERS[reviewer_name]` — if found, wrap in `EnsembleReviewer` and dispatch.
2. Check `WORKERS[reviewer_name]` — if found, wrap in `SingleWorker` and dispatch.
3. Else raise `ConfigError(f"unknown reviewer: {reviewer_name}")`.

**Discussion-phase bulk guard:** If the resolved reviewer uses a bulk-mode worker and `phase == "discussion"`, the engine raises `ConfigError` before spawning anything. No `discussion-review-bulk.md` template exists; bulk is only defined for `plan` and `code` phases.

**Validate-before-mkdir (Fix E):** Reviewer name validation and the discussion-bulk guard run before any directory creation. A bad reviewer name does not create `_millhouse/scratch/reviews/`.

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

`_millhouse/config.yaml` contains a `review-modules:` block that names reviewers by phase:

```yaml
review-modules:
  discussion:
    default: sonnet
  plan:
    default: opus
  code:
    default: ensemble-gemini3pro-x2-opus
```

Each value (`sonnet`, `opus`, `ensemble-gemini3pro-x2-opus`) is either a `WORKERS` key or a `REVIEWERS` key. The engine treats both syntactically identically — the registry lookup determines the actual dispatch shape.

Per-round overrides follow the key `<round-number>:` under the phase, e.g.:

```yaml
review-modules:
  plan:
    default: opus
    2: opusmax
```

`millpy.core.config.resolve_reviewer_name(cfg, phase, round)` implements the lookup: try `review-modules.<phase>.<round>` first, then `review-modules.<phase>.default`.

## Fallback to legacy config

`resolve_reviewer_name` applies a two-level preference rule:

1. `review-modules.<phase>.<N>|default` (new block — wins if present).
2. `models.<phase>-review.<N>|default` (legacy block — used as fallback when the new block is absent or the key is missing).

The legacy `models:` keys are preserved so `mill-setup`'s auto-seed does not fight the config file. They are not read by the millpy engine when the new block is present.

## Adding a new worker or ensemble

To add a new atomic worker, add one entry to `WORKERS` in `millpy/reviewers/workers.py`. To add a new ensemble, add one entry to `REVIEWERS` in `millpy/reviewers/definitions.py`. Import-time validation will catch any reference errors at the next `import millpy.reviewers`.

Do not add entries to the legacy `reviewers:` YAML block in `_millhouse/config.yaml` — that block is unused by the millpy engine and preserved only to avoid fighting `mill-setup`.
