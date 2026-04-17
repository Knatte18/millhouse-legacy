# Tasks

## Move tasks.md to orphan branch `tasks` (stop main-branch commit churn)

`tasks.md` lives on main today, so every task reshuffle pollutes main's history. Move it to an orphan branch `tasks` that never merges into main. Git-synced across machines, viewable on GitHub via `github.com/Knatte18/millhouse/blob/tasks/tasks.md`, editable locally via a dedicated worktree.

**Scope:**

1. Create orphan branch `tasks` with only `tasks.md` at root. Remove `tasks.md` from main.
2. Add a `tasks.worktree-path` pointer to `_millhouse/config.yaml` (default: `../<repo>-tasks`).
3. Update `mill-setup` to run `git worktree add <tasks-worktree-path> tasks` if the worktree does not already exist. Idempotent.
4. Rework every skill/script that currently reads or mutates `tasks.md` so it resolves the path via config, not via cwd. Affected: `mill-spawn` (claim-and-remove), `mill-start` (claim path 2/3/4), `mill-merge` (write `[done]`), `mill-add` (append), `mill-abandon` (write `[abandoned]`), `mill-inbox` (append imported issues), and `spawn_task.py` / any `millpy` helpers that touch tasks.md. All writes must go through `git -C <tasks-worktree-path> add/commit/push`.
5. Document the new workflow in `CLAUDE.md` and the relevant skill docs (open a dedicated VS Code window on the tasks worktree to read/edit tasks).

**Why phase-1-only:** this task stops the main-branch commit churn and keeps GitHub-sync. The longer-term move to "GH issues as source of truth with tasks.md as a generated view" is part of the Self-reinforcement loop task below. Land this first so the Self-reinforcement task only has to change the content model, not the storage location.

## Track task state across machines (W4 — needs design)

Invert the `_millhouse/` gitignore so task state (discussion, plan, status, reviews) travels with the branch. Motivated empirically by the millpy task's Step 33, where a gitignored `config.yaml` silently dropped out of an atomic bundle commit. Do not start implementation until the open design questions in the proposal are answered (gitignore granularity, commit cadence, config split, two-machine race handling, `mill-merge` cleanup contract).

**Design doc:** [plugins/mill/doc/proposals/04-track-task-state.md](plugins/mill/doc/proposals/04-track-task-state.md)

## Plan format + review architecture rewrite

- tags: [enhancement, mill-plan, reviewer]
- Consolidates issue #38 (drives), #35 (superseded by #38, folded), #36 (extended by #38, folded), and #34 (folded into the per-card-review question below).
- Introduces a cleaner plan-format contract: `depends-on` = logical deps only; write-safety auto-inferred from `modifies`/`creates`; reviewers stop flagging shared-modifies; `reads` no longer duplicates `modifies` (`Explore ⊆ (Reads ∪ Modifies)`).
- New module `plugins/mill/scripts/millpy/core/plan_dag.py` with `build_enriched_dag(card_index)`.
- Updates: `plan_validator.py` Explore subset rule; `doc/prompts/plan-review.md` holistic prompt; `doc/formats/plan.md` contract section; `mill-go` executor to consume enriched DAG; `mill-plan` SKILL.
- **Background doc:** [plugins/mill/doc/proposals/05-plan-format-contract.md](plugins/mill/doc/proposals/05-plan-format-contract.md)
- No runtime per-file lock layer — single source of truth is the enriched DAG.

**Open design question — per-card review: remove entirely, or gate?**

Originally scoped as "gate per-card review behind a `per-card-threshold` (default 20)". Revisit in light of 2026-04-17 observations and the Planner-grouped review task below — per-card may have no niche left worth the code surface.

- **Option A — remove entirely.** Delete all per-card review code, config keys (`pipeline.*-review.per-card`), and `dispatch: bulk` reviewer definitions scoped to per-card. Small plans get holistic; large plans go to Planner-grouped review once that lands. Simplest architecture; smallest code surface. Current footprint: 10 files under `scripts/millpy/` (engine, workers, plan_validator, plan_review_loop, dag, config, entrypoints, tests).
- **Option B — gate behind threshold.** Keep per-card but only activate above N cards (default 20). Preserves current behavior as opt-in. Keeps the reviewer/DAG/config code that is otherwise unused day-to-day.
- **Option C — gate now, sunset later.** Land gating as a transition; remove in a follow-up once Planner-grouped review proves out.

Context favoring removal:

- Gemini-backend task observed (2026-04-17) that single-worker per-card on 6 cards already hit free-tier quota. Per-card × ensemble is effectively unusable on free tier. Holistic stays safe.
- Planner-grouped plan review (task below) is designed to replace per-card for 30+ card plans.
- mill-go linear-default task (below) removes Builder-level parallelism — per-card reviewer fan-out no longer matches any other parallelism in the system.
- The only range where per-card earns its keep today is ~20–30 cards, a narrow band likely covered by grouped review once it lands.

Resolve this question during this task's discussion phase before implementing.

## Planner-grouped plan review for large plans

- tags: [enhancement, mill-plan]
- When a plan has 30+ cards, per-card bulk review + holistic tool-use review may not catch inter-group issues effectively. Add an optional Planner-grouped review mode where Planner creates ad-hoc review groups (overlapping subsets of cards) and spawns one reviewer per group in parallel. Same card can appear in multiple groups. Pure Planner-side change — no plan format changes needed.
- Orthogonal to "Plan format + review architecture rewrite" above. Land that first; re-evaluate the grouped approach after.

## mill-go Builder-tweaks: session-resume + linear default

- tags: [enhancement, mill-go]
- Two small changes to mill-go's Builder execution. Both touch the same code path and merit one task.

**1. Resume implementer session on REQUEST_CHANGES (#37)**

Today mill-go spawns a fresh Sonnet session on `REQUEST_CHANGES` instead of resuming the session that wrote the original code. The comment "null for current CLI" in [mill-go/SKILL.md:229-236](plugins/mill/skills/mill-go/SKILL.md#L229-L236) is outdated — [spawn_agent.py:89-90](plugins/mill/scripts/millpy/entrypoints/spawn_agent.py#L89-L90) already supports `--session-id` and [spawn_agent.py:207, 224, 258](plugins/mill/scripts/millpy/entrypoints/spawn_agent.py#L207) already emits `session_id`. mill-go just never captures or reuses it.

Fix:

1. After the first implementer spawn for a card, parse `session_id` from the spawn's JSON output. Persist it per card (e.g. `status.md` entry `card_<N>_session_id: <id>`).
2. On `REQUEST_CHANGES`, resolve the card's `session_id` and spawn with `spawn_agent.py --session-id <id>`.
3. Fallback to a fresh Sonnet session only if `session_id` is missing or `claude --resume` fails.
4. Update [mill-go/SKILL.md:229-236](plugins/mill/skills/mill-go/SKILL.md#L229-L236) to describe resume as primary, fresh as fallback.

Benefits: context bevaring (implementer knows why it made each choice), token savings (prompt-cache hits within 5 minutes give ~90% discount), faster iteration.

Open questions:

- Session lifetime — how long before a session is too stale to resume?
- Session death handling — fall back to fresh and log.
- Per-card vs. per-run session — stay per-card (current implicit model)?

**2. Linear execution as default; DAG-parallel as opt-in**

Observed 2026-04-17: running Builder linearly on a multi-card plan was fast enough and simpler to follow than parallel DAG execution. Parallel-DAG code path has bugs and extra complexity that do not earn their keep for the plan sizes we run today.

Fix:

1. Add `pipeline.executor.parallel` to `_millhouse/config.yaml` (default `false`). Or a CLI flag (`--parallel`).
2. mill-go default execution mode: linear, single-threaded — cards in DAG order, one at a time.
3. Keep all DAG-parallel infrastructure intact — it stays behind the flag for future reactivation.
4. Document the default in `mill-go/SKILL.md`.

No removal of DAG code. The `plan_dag.py` work from the Plan-format task stays useful for linear ordering — just without the concurrency.

## Plugin-doc path resolution: references must work from installed-plugin context

- tags: [bug, docs]
- All references in skill files, prompt templates, and doc files that use the `plugins/mill/...` prefix (doc/, scripts/, templates/) work when Millhouse is the repo being worked on, but break when Millhouse is installed as a Claude plugin in another repo — the installed files live at `~/.claude/plugins/cache/millhouse/mill/<version>/...`, not at `plugins/mill/...` relative to the user's cwd.
- Approximate scale: ~127 occurrences across ~40 files (skills, doc, prompts, templates, tests).
- Requires a design decision on the resolution convention before the sweep:
  - **A.** Relative-to-SKILL paths (e.g. `../../doc/formats/plan.md` from a SKILL file).
  - **B.** `<PLUGIN_ROOT>` token, resolved by Claude from the "Base directory for this skill" hint.
  - **C.** Three-tier resolution documented in each SKILL (like `mill-spawn/SKILL.md` does for `spawn_task.py`).
  - **D.** Runtime resolver helper — a millpy function Claude is instructed to call to resolve logical doc names.
- Scope: pick a convention in the discussion phase, then sweep every reference. Keep the change mechanical once the convention is locked.
- Out of scope: code-only references like `millpy.core.paths.repo_root` (Python symbols resolved via `PYTHONPATH`) — only the file-path text references that Claude or humans open via a path string.
- **Observed 2026-04-17** during the "mill-spawn / mill-vscode / mill-terminal: subfolder + nested-repo fixes" task discussion, while fixing dead `doc/modules/*` link targets. That sibling task left the prefix form unchanged (`plugins/mill/doc/...`); this task finishes the job.
