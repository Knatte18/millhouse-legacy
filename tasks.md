# Tasks

## mill-go v2 (W3) — three-skill split + DAG-aware executor

Second half of the rewrite. Splits today's `mill-go` into `mill-start` / `mill-plan` / `mill-go` with a pre-arm wait pattern. Rewrites `mill-go` as a DAG-aware layer-parallel executor: Thread A (Opus, in `mill-plan`) owns WHAT by writing cards with `depends-on:` metadata; Thread B (Opus, in `mill-go`) owns HOW by building the DAG, spawning Sonnet sub-agents per layer, running pytest per layer, and handling receiving-review. Adds a lightweight independence-signal check in `mill-start` Phase: Discussion (only prompts when the discussion touches pieces that genuinely need different merge schedules, cross-repo boundaries, or independent rollback — not a size-based heuristic, since W2's batching solves the size axis). Sets Sonnet as the default implementer floor with Haiku out of the default pipeline. Ships as a v2 batch-plan in the format delivered by W2 (dogfood #1 of the new format).

**Design doc:** [plugins/mill/doc/proposals/03-mill-go-v2.md](plugins/mill/doc/proposals/03-mill-go-v2.md)


## Track task state across machines (W4 — needs design)

Invert the `_millhouse/` gitignore so task state (discussion, plan, status, reviews) travels with the branch. Motivated empirically by the millpy task's Step 33, where a gitignored `config.yaml` silently dropped out of an atomic bundle commit. Do not start implementation until the open design questions in the proposal are answered (gitignore granularity, commit cadence, config split, two-machine race handling, `mill-merge` cleanup contract).

**Design doc:** [plugins/mill/doc/proposals/04-track-task-state.md](plugins/mill/doc/proposals/04-track-task-state.md)
