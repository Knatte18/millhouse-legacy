# Proposal 05 — Plan Format + Review Architecture: cleaner contract

**Status:** Needs design — rough contract agreed; details to settle during implementation.
**Task entry:** `tasks.md` → "Plan format + review architecture rewrite".
**Supersedes on GH:** #35 (folded), extends #36 (folded), folds #34.
**Drives:** #38.
**Depends on:** none.
**Priority:** High — removes recurring noise in plan-review rounds and simplifies Planner's job.

## One-line summary

Clean up the plan format so `depends-on` carries only logical dependencies, write-safety is auto-inferred by Planner from `modifies`/`creates`, `reads` never duplicates `modifies`, reviewers stop flagging write-safety as BLOCKING, and per-card plan review is gated by a card-count threshold so small plans skip it.

## Empirical motivation

Observed during the `general-bugfix-sweep` plan-review session on 2026-04-16 (13-card plan, 3 review rounds, ~$1.50 per round with per-card fan-out):

- Holistic sonnetmax (tool-use) caught every BLOCKING finding that per-card reviewers caught, plus cross-card DAG conflicts that per-card reviewers structurally cannot see.
- 4 review rounds were spent chasing the same pattern: cards 3/9, 6/10, 7/11, 3/12, 11/12 all needed manual ordering `depends-on` entries only because they shared a file. That is not logic — it is write-safety.
- Planner was forced to list files in both `modifies` and `reads` because the `plan_validator` subset rule required it. The redundancy added visual noise without encoding new information.

Conclusion: Planner's cognitive load on write-safety deps is avoidable; reviewer is duplicating concerns that should be Planner-automatic; reads/modifies redundancy is a validator artifact.

## The cleaner contract

### 1. `depends-on` = logical deps ONLY

A card lists another in `depends-on` if and only if the latter's output is required as the former's input (e.g. "card B imports a constant that card A defines"). Planner writes this; reviewer verifies it against the task's logic.

Write-safety ordering is no longer a `depends-on` concern.

### 2. Write-safety ordering is Planner-internal, auto-derived

Planner builds its execution DAG by unioning:

- **Logical edges:** declared `depends-on` entries from each card.
- **Write-safety edges:** auto-inferred from `modifies` + `creates`. For any file with 2+ cards touching it, the plan-builder injects an ordering edge `(lower-card-number, higher-card-number)` — deterministic, no ambiguity.

The enriched DAG is what `mill-go` executes. The card overview in the plan continues to show only explicit `depends-on` (Planner-authored, logical). No runtime safety net needed — correct DAG → safe execution.

**Design decision: no runtime per-file lock layer.** Earlier discussion (#35) proposed a belt-and-suspenders runtime lock in the mill-go executor. This is dropped. Single source of truth (the enriched DAG) beats duplicating correctness in two places. If the enriched DAG is wrong, fix `plan_dag.py`, not the executor.

### 3. Reviewers stop flagging shared-modifies as BLOCKING

`plugins/mill/doc/prompts/plan-review.md` holistic prompt drops the "two cards modify same file without dep" rule. That is Planner's concern now, handled automatically by `plan_dag.py`. Reviewer trusts Planner's enriched DAG for write-safety. If the enriched DAG has bugs, that is a `plan_dag` issue tracked separately — not a plan-content issue to re-surface in every review.

### 4. `reads` does not duplicate `modifies`

Today the plan format has both listing the same files redundantly. Example: in the bugfix-sweep plan, card 3 listed `scripts/millpy/entrypoints/spawn_task.py` in both `modifies` and `reads`.

**Cause.** `plan_validator` enforces `Explore ⊆ Reads`. If the Explore section references a file that is also modified, Planner must list it in Reads to satisfy the validator. That forces the redundancy.

**Fix.** Change the subset rule to `Explore ⊆ (Reads ∪ Modifies)`. Planner lists each file once in whichever field fits:

- `modifies` — the card changes the file. Reading it is implicit.
- `reads` — pure context, not changed and not created.
- `creates` — fresh file. Usually not also read.

Effective context set = `reads ∪ modifies` is a computed view, not declared.

### 5. Per-card review gated by threshold

Per-card plan review fans out N reviewer spawns per plan (one per card, plus 1 holistic). For a 13-card plan that is 14 spawns per round. Holistic alone caught every BLOCKING finding the per-card reviewers found, plus DAG conflicts they could not see.

**Change.** Introduce `pipeline.plan-review.per-card-threshold` (default `20`) in `_millhouse/config.yaml`. Below threshold: holistic only. At or above threshold: holistic + per-card fan-out.

**Complement.** Rebalance the holistic prompt (#36) so it focuses on cross-card and architectural concerns (constraint violations, design-decision alignment, DAG correctness, overall completeness, batch graph integrity). Leave per-card concerns (atomicity, testability, reads-completeness, step granularity, Explore⊆{Reads∪Modifies}) to the per-card reviewers when they run.

Holistic and per-card become complementary rather than overlapping.

## Implementation sketch

New module `plugins/mill/scripts/millpy/core/plan_dag.py`:

- `build_enriched_dag(card_index) -> DAG` — unions logical `depends-on` edges with auto-inferred same-file edges.
- Returns a typed DAG object that `mill-go` can consume directly.
- Includes a `debug_dump()` method for when reviewers or the user want to inspect the auto-inferred edges.

`plugins/mill/scripts/millpy/core/plan_validator.py` updates:

- Change the Explore subset check to `Explore ⊆ (Reads ∪ Modifies)`.
- Drop any enforcement that pushes toward reads/modifies overlap.

`plugins/mill/doc/prompts/plan-review.md` holistic prompt:

- Remove the "two cards modify same file without dep" rule.
- Rebalance per #36 to focus on cross-card and architectural concerns.

`plugins/mill/doc/prompts/plan-review-per-card.md`:

- Keep as-is, but ensure its scope matches the rebalanced holistic (no gap, no overlap).

`plugins/mill/scripts/millpy/entrypoints/spawn_reviewer.py` or mill-plan SKILL:

- Read `pipeline.plan-review.per-card-threshold`.
- If `card_count < threshold`: skip per-card fan-out, run holistic only.
- If `card_count >= threshold`: run both.

`mill-go`:

- Call `build_enriched_dag(card_index)` to get the DAG.
- Execute layer by layer as today — the DAG is the only source of truth for ordering.

`mill-plan` SKILL:

- Document Planner as the owner of write-safety.
- Clarify that `depends-on` in overview cards is logical only.
- Reference this proposal from the Phase: Plan description.

`plugins/mill/doc/formats/plan.md`:

- Update the contract section:
  - `reads` = additional context files NOT in modifies/creates.
  - `depends-on` = logical deps only; write-safety is automatic.
  - New validation rule: `Explore ⊆ (Reads ∪ Modifies)`.

## Design questions to settle during implementation

- Cycle detection — auto-inferred edges cannot introduce cycles (they always point from lower card-number to higher), but the union with logical edges could. Validator must reject cycles and name them.
- What about `creates` vs `modifies` on the same file across cards (card A creates, card B modifies)? Auto-infer a `create → modify` edge. Validator flags `modify → create` as an error.
- Holistic prompt under 30 cards vs over 30 — does the threshold stay at 20? Tune empirically after first few plans run under the new scheme.
- How does this interact with Planner-grouped review (`tasks.md` → "Planner-grouped plan review for large plans")? Planner-grouped is a further refinement for very large plans — land this proposal first, re-evaluate the grouped approach after.

## Benefits

- Planner writes ~40% fewer `depends-on` entries (logical only).
- Eliminates the "two cards share file without dep" class of reviewer findings entirely.
- Plan format reads cleaner — no duplicate file listings between reads and modifies.
- Clearer separation of concerns: Planner owns correctness of the DAG, reviewer owns logical completeness of the plan against the task scope.
- ~13× cost reduction on small-plan reviews (below threshold).
- Single source of truth for DAG — no runtime layer drift.

## Related

- Supersedes #35 (extends with points 3–5, drops runtime layer).
- Extends #36 (holistic prompt rebalance — removing "same-file" rule aligns with that).
- Folds #34 (per-card threshold).
- Coexists with "Planner-grouped plan review for large plans" task in `tasks.md` (orthogonal refinement for very large plans).
