# Tasks

## [active] Plan-format v2 (W2) — batch-plan directories, planner, reviewer

First half of the mill-go v2 rewrite. Replaces `_millhouse/task/plan.md` with a `_millhouse/task/plan/` directory (overview + per-batch files) and adds per-card `depends-on:` / `touches-files:` metadata. Teaches `mill-plan` to write the new format. Rewrites plan review to run per-batch with a Flash/Sonnet/Opus ensemble. Adds a "language-specific pitfalls" criterion to `plan-review.md` to catch the class of blind spot that let `core/logging.py` slip past three reviewers during the millpy task. Ships as a single v1 plan because the v2 format does not exist yet.

**Design doc:** [plugins/mill/doc/proposals/02-plan-format-v2.md](plugins/mill/doc/proposals/02-plan-format-v2.md)


## mill-go v2 (W3) — three-skill split + DAG-aware executor

Second half of the rewrite. Splits today's `mill-go` into `mill-start` / `mill-plan` / `mill-go` with a pre-arm wait pattern. Rewrites `mill-go` as a DAG-aware layer-parallel executor: Thread A (Opus, in `mill-plan`) owns WHAT by writing cards with `depends-on:` metadata; Thread B (Opus, in `mill-go`) owns HOW by building the DAG, spawning Sonnet sub-agents per layer, running pytest per layer, and handling receiving-review. Adds a lightweight independence-signal check in `mill-start` Phase: Discussion (only prompts when the discussion touches pieces that genuinely need different merge schedules, cross-repo boundaries, or independent rollback — not a size-based heuristic, since W2's batching solves the size axis). Sets Sonnet as the default implementer floor with Haiku out of the default pipeline. Ships as a v2 batch-plan in the format delivered by W2 (dogfood #1 of the new format).

**Design doc:** [plugins/mill/doc/proposals/03-mill-go-v2.md](plugins/mill/doc/proposals/03-mill-go-v2.md)


## Track task state across machines (W4 — needs design)

Invert the `_millhouse/` gitignore so task state (discussion, plan, status, reviews) travels with the branch. Motivated empirically by the millpy task's Step 33, where a gitignored `config.yaml` silently dropped out of an atomic bundle commit. Do not start implementation until the open design questions in the proposal are answered (gitignore granularity, commit cadence, config split, two-machine race handling, `mill-merge` cleanup contract).

**Design doc:** [plugins/mill/doc/proposals/04-track-task-state.md](plugins/mill/doc/proposals/04-track-task-state.md)
