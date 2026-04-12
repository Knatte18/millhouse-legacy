# Proposal 05 — Dual-Opus Orchestrator

**Status:** Proposed
**Depends on:** Proposal 04 (three-skill split). Strongly benefits from Proposal 01 (ensemble reviewer) being in place first.
**Blocks:** none

## One-line summary

Make `mill-go`'s Thread B an **Opus orchestrator** instead of a Sonnet implementer-orchestrator. Opus stays the brain across both planning and execution. Code edits are always delegated to fresh Sonnet/Haiku subprocesses ("implementer" for the original plan, "fixer" for review-fix loops). Code-review feedback is decided by Opus, not by the cheap implementer.

## Background

### The capability/cost mismatch in today's design

Today's split:

- **Thread A** (mill-plan, after Proposal 04 — was mill-go P2): Opus. Writes the plan, runs plan review. Owns design judgment.
- **Thread B** (mill-go P3): **Sonnet**. Implements the plan, then **also handles code-review feedback**: applies the receiving-review decision tree, decides FIX vs PUSH-BACK, applies fixes, re-spawns the reviewer.

The asymmetry: the **judgment-heavy** stage of the run (deciding which review findings to fix vs. push back vs. negotiate against) is handled by the **less capable** model. The mechanical implementation work (typing patches into files) is handled by the same model. That's backward from a capability/cost standpoint.

### Why receiving-review is judgment-heavy

The `mill-receiving-review` skill defines a three-step decision tree per finding:

1. **VERIFY:** Is this finding accurate? Cite the actual code if not. Requires close reading and judgment about reviewer correctness.
2. **HARM CHECK:** Does fixing this break documented design intent? Does it conflict with a `### Decision:` in the plan's `## Context`? Does it destabilize out-of-scope code? Requires understanding of the plan's design rationale.
3. **PUSH BACK with cited evidence**, or FIX. Requires standing one's ground against another model that may be confidently incorrect. This is the failure mode of weaker models — they default to "FIX IT" because pushing back feels confrontational.

Sonnet does ~80% of this fine, but defaults to FIX on the cases where Opus would correctly push back. You lose the brake that prevents a confident-but-wrong reviewer from rewriting the implementation in the wrong direction.

### The core insight

**Opus should never type code. Sonnet/Haiku should never make design decisions.** Each role's failure mode is contained:

| Role | Model | Job | Why this model |
|---|---|---|---|
| Thread A planner | Opus (mill-plan) | Discussion + plan + plan review | Design judgment, alternatives, decisions |
| Thread B orchestrator | **Opus (mill-go)** | Spawn implementer, spawn reviewer, decide on review feedback, spawn fixer, merge | Design judgment in the receiving-review tree, plan-format authoring for fix loops |
| Implementer | Sonnet/Haiku (one-shot per plan) | Mechanical execution from atomic plan card | The plan-format's atomicity invariant makes this work for a fast model |
| Reviewer ensemble | Gemini ×3 + Opus handler (Proposal 01) | Read diff, find issues, synthesize | Vendor-diverse, ensemble cancels noise |
| Fixer | Sonnet/Haiku (one-shot per fix loop) | Mechanical execution from a fixer plan written by Thread B | Fixer plans are small, atomic, and self-contained |

This proposal's core change: **Thread B becomes Opus**. The current Sonnet implementer-orchestrator role splits into two:

- **Orchestrator** (Thread B, Opus, alive across all of P3) — never edits code itself, only orchestrates.
- **Implementer/Fixer** (fresh Sonnet/Haiku subprocess, one-shot per plan) — does all the typing.

### Why fresh subprocesses for the implementer/fixer

The implementer reads a plan (the original one for the first run, or a small fixer plan for each review-fix round) and exits when done. It never needs to remember anything across runs. Each spawn is a clean cold-start with a focused, small input. This:

- Keeps the implementer's context window tiny (just the plan card + relevant files).
- Avoids any risk of context bloat across multiple phases.
- Lets the implementer be a cheap Sonnet or even Haiku — the plan-format's verbose-is-feature philosophy already works for that capability tier.
- Naturally limits the blast radius if the implementer makes a mistake — it's just one focused spawn that can be re-run.

### Why the orchestrator stays warm (alive across P3)

Thread B keeps its in-memory context across the whole P3 run because:

- It needs to maintain a coherent picture of "what's been done, what's left, which findings have been resolved, which are in dispute".
- It needs the design rationale from the plan to apply HARM CHECK reliably.
- Re-cold-starting Thread B between phases (implementer-spawn, reviewer-spawn, fixer-spawn) would force re-reading discussion + plan + status every time. Token cost adds up fast.
- Most of Thread B's wall-clock time is **idle** waiting on subprocesses. Token budget for active reasoning is small.

### Context budget for Thread B

The biggest concern with Opus-Thread-B is context bloat across multiple review rounds. Calculation:

- **Plan + discussion + brief load:** ~30k tokens at start
- **Per review round, with ensemble (Proposal 01):** ~5k tokens (the synthesized combined report from the handler — Thread B never sees the raw N reviewer reports, that's the handler's job)
- **Per review round, without ensemble:** ~15k tokens (the raw single-shot reviewer report)
- **Per fix loop iteration:** ~3k tokens (the fixer plan Thread B writes, plus the implementer's exit JSON)
- **Status.md polling:** negligible

**With ensemble + 3 review rounds + 3 fix iterations:** ~30k + (5k × 3) + (3k × 3) = ~54k tokens of active context. Well within Opus's budget, plenty of headroom.

**Without ensemble + 3 review rounds + 3 fix iterations:** ~30k + (15k × 3) + (3k × 3) = ~84k tokens. Still workable but tighter.

This is **why Proposal 01 is a strong prerequisite** — it dramatically improves Thread B's context efficiency by moving raw report bloat into the disposable handler thread.

### Why fixer plans reuse the plan-format

When Thread B applies the receiving-review decision tree and decides which findings to FIX, it needs to generate work for the fixer. The cleanest way is to write a small "fixer plan" using the same `plan-format.md` schema as the original plan: atomic step cards with `Modifies:`, `Explore:`, `Requirements:`, `Commit:` (or batch boundary if Proposal 03 lands).

**Why:**

- One mental model. The fixer doesn't need a new schema to learn; it reads the same kind of document the original implementer reads.
- The atomicity invariant carries over for free.
- Plan-review machinery (Proposal 01's ensemble) can also be applied to fixer plans if they get large enough.
- The fixer can be the same code path as the implementer — just re-spawned with a different plan file path.

## Goals

1. Restructure `mill-go` so it owns Thread B as an **Opus orchestrator**, not the Sonnet implementer-orchestrator.
2. Split the current `implementer-brief.md` into two briefs:
   - **Orchestrator brief** (Thread B, Opus): orchestrate spawns, apply receiving-review decision tree, write fixer plans, decide merge.
   - **Implementer brief** (Sonnet/Haiku, one-shot): read a plan card, implement it, commit, exit.
3. Add a "fixer" mode to the implementer brief — same brief, but the input plan is a fixer plan instead of the original plan. Programmatically the same; semantically different.
4. Move the receiving-review decision tree application into the orchestrator's responsibilities. Thread B reads the (synthesized, if ensembled) review report, applies the tree, produces a decision report, and writes a fixer plan based on the FIX decisions.
5. Update the `_millhouse/config.yaml` `models:` block to support: `orchestrator: opus`, `implementer: sonnet | haiku`, `fixer: sonnet | haiku`, in addition to the existing `code-review`/`plan-review`/`discussion-review` slots.
6. Update resume protocols so a crashed Thread B can be re-spawned by `mill-go --resume` with the same context (read plan + discussion + status + last review report from disk).
7. Update mill-status to display the new role hierarchy (orchestrator + active subprocess if any).
8. Apply the autonomous-fix policy from Proposal 02 to the new orchestrator brief (the orchestrator can fix its own tools; the implementer/fixer cannot).

## Non-goals

- Changing the plan format. (Proposal 03.)
- Changing the reviewer. (Proposal 01.)
- Changing the skill split. (Proposal 04.)
- Adding parallel execution. (Proposal 06.)
- Eliminating the orchestrator (i.e., serverless / no long-running thread). Doable in principle but a much bigger redesign with no clear win.

## Design decisions

### Decision: Thread B is Opus, alive across all of P3

See "Why the orchestrator stays warm" above.

**Alternatives rejected:**

- **Thread B is Sonnet, but spawn an Opus subprocess for receiving-review** (the "tiered fix-decision spawn" alternative from earlier discussion). Cheaper but adds a spawn round-trip per review round, and Thread B still has to coordinate the spawn. Net: more complexity for marginal cost savings. Rejected.
- **Thread B is Opus, but exits between phases and re-spawns** (cold-start each phase). Saves idle cost, but pays cold-start cost (re-reading discussion + plan) on every re-spawn. Net: usually worse.
- **Thread B is Sonnet** (today's design). Loses the HARM CHECK quality, which was the whole motivation.

### Decision: Implementer and fixer are the same brief, different inputs

The fresh subprocess that types code reads the same brief (focused, mechanical, no judgment). The only difference is which plan file it reads. For the original plan: `plan.md`. For a fix loop: `fix-plan-r<N>.md` (where N is the round number).

**Why:** One brief, one mental model. Reduces brief maintenance burden. Removes any risk of "wait, is this the implementer brief or the fixer brief" confusion.

**Alternatives rejected:** Two separate briefs (more to maintain, more failure modes).

### Decision: Thread B writes the fixer plan in the same `plan-format.md` schema

See "Why fixer plans reuse the plan-format" above.

**Alternatives rejected:** A separate, lighter "fixer-instruction format" — saves some structure but loses the atomicity invariant and forces a new mental model.

### Decision: The orchestrator (Thread B) blocks on each subprocess synchronously

Thread B spawns the implementer, blocks until completion. Spawns the reviewer (or the ensemble handler), blocks until completion. Spawns the fixer, blocks until completion. No concurrent subprocesses managed by Thread B at any point.

**Why:** Sequential is far simpler to reason about, debug, and resume. Concurrency is the source of most distributed-system bugs. The wall-clock cost of sequential execution is usually small because each phase has to finish before the next can sensibly start anyway.

**Alternatives rejected:** Concurrent subprocess management (parallel implementer + speculative reviewer, etc.) — defer to a much later proposal if there's clear value.

### Decision: Resume protocol stores `current_subprocess` in status.md

When Thread B spawns a subprocess, it writes to `status.md`:

```yaml
phase: implementing
current_subprocess:
  role: implementer
  pid: 12345
  started: 2026-04-13T08:30:00Z
  plan: _millhouse/task/plan.md
```

On resume after crash, a fresh Thread B reads this and decides:

- If `current_subprocess.pid` is still alive: re-attach via Monitor and continue.
- If dead: read the subprocess's exit state from status.md (which it should have written before exit), determine whether the subprocess work was completed, and re-spawn or skip accordingly.

**Why:** Today's resume reads `phase:` and routes based on it. With multiple subprocess types, `phase:` alone is ambiguous (e.g. `phase: reviewing` could mean "reviewer running" or "reviewer done, applying decisions"). The `current_subprocess` field disambiguates.

### Decision: The orchestrator (Thread B) uses Opus's "thinking mode" sparingly

Opus's extended thinking budget is finite per session. Thread B should default to standard mode and only enable thinking for explicit judgment-heavy steps: applying the receiving-review tree, designing a non-trivial fixer plan. Routine spawns and status updates should not consume thinking budget.

**Why:** Token budget hygiene over a long-running orchestrator session.

### Decision: Naming and role labels

Drop the "Thread A / Thread B" nomenclature in user-facing docs. Use:

- **Planner** (was Thread A, mill-plan): writes the plan, runs plan review.
- **Orchestrator** (new Thread B, mill-go): orchestrates implementation and review-fix loops.
- **Implementer** (fresh subprocess from orchestrator): runs the original plan.
- **Fixer** (fresh subprocess from orchestrator): runs a fix-plan generated by the orchestrator.
- **Reviewer ensemble** (Gemini ×N + Opus handler): the review machinery.
- **Reviewer handler** (Opus, fresh subprocess per round): synthesizes the ensemble outputs.

**Why:** "Thread A / Thread B" was already strained when there were only two roles. With five role types, the nomenclature breaks down. Plain English names are clearer.

## Open questions for the discussion phase

1. **Cost benchmarking** — what does a typical Opus orchestrator session actually cost in wall-clock idle vs. active token use? Need real numbers from a small pilot run before committing to the design.
2. **Fixer plan size threshold** — at what point does a fixer plan get its own plan-review pass? A 2-step fixer plan probably doesn't need it. A 10-step one probably does. Configurable threshold? Default `reviews.fixer-plan-min-steps: 5`?
3. **Should the orchestrator be allowed to *modify* the original plan mid-run?** E.g. if a review finding reveals the original plan was incomplete, can Thread B add steps to `plan.md` and re-run from there? Or must it always go via fixer plans? Probably must go via fixer plans, to preserve the original plan as the design contract.
4. **What if the implementer/fixer hits a tool bug** (the autonomous-fix scenario from Proposal 02)? The implementer is supposed to be purely mechanical. Should it ever be allowed to fix its own tools, or should it always block and surface to the orchestrator? Probably: implementer always blocks, orchestrator decides what to do (which may include spawning a one-step fixer to fix the tool, then resuming the implementer).
5. **How does the orchestrator know the implementer is "done correctly"?** Today: implementer exits with `phase: complete` JSON. New: orchestrator should also verify via `git log` that the expected commits exist, before proceeding to review.
6. **Status.md schema migration** — the `current_subprocess` field is new. Existing tooling (mill-status) needs to know how to read it.
7. **What model is the fixer subprocess?** Same as the implementer (Sonnet/Haiku)? Or always Sonnet (avoid Haiku for fixes since they're potentially more delicate)? Probably configurable: `models.fixer: sonnet` by default.
8. **Naming again** — "Planner" / "Orchestrator" feel right but verify with use. Bikeshed-prone.

## Acceptance criteria

- A run with `models.orchestrator: opus` and `models.implementer: sonnet` produces the same final code state as today's run, with cleaner role separation observable in status.md and logs.
- During a code-review round, the orchestrator reads the (synthesized) review report and the plan, applies the receiving-review tree, produces a `fix-plan-r<N>.md` for any FIX decisions, spawns a fixer subprocess, blocks on it, and re-spawns the reviewer.
- A reviewer finding that contradicts a documented `### Decision:` in the original plan results in a PUSH BACK from the orchestrator (cited evidence in the fixer report), not a silent FIX.
- Crash mid-implementer: orchestrator restart resumes by detecting the dead subprocess, reading the partial commits from git, and re-spawning the implementer with `--resume` if needed.
- mill-status displays the orchestrator + active subprocess hierarchy.
- Token cost over a 3-round-fix run with ensemble reviewer is measured and within ~2× the cost of today's Sonnet-orchestrator design (acceptable for the quality lift).

## Risks and mitigations

- **Cost surprise.** Idle Opus context across an hour-long run could be expensive even when active token use is low. Mitigation: pilot on a small task first, measure, tune thinking-mode usage, set a hard ceiling on orchestrator session duration.
- **Resume protocol regressions.** The `current_subprocess` field is new and adds branches. Mitigation: explicit test matrix for crash-recovery scenarios.
- **Implementer/fixer parity drift.** If the implementer brief and the fixer brief are "the same" but tested separately, they can drift apart in subtle ways. Mitigation: literally the same file, same template, with the only difference being the `<PLAN_PATH>` substitution.
- **Orchestrator context bloat over many review rounds.** Mitigation: Proposal 01 (ensemble + handler) is the primary defense. Without it, orchestrator should fall back to single-shot review with `code-review.report-summary-only: true` so it doesn't consume the full reviewer report.
- **Naming churn confusing the user during the rollout.** Mitigation: keep "Thread A / Thread B" as aliases in the docs for one release, then drop them.

## Dependencies

- Proposal 04 (three-skill split) — this proposal restructures `mill-go`'s implementation but needs the skill-level split as a foundation. They could land together, but Proposal 04 is the smaller change and should land first.
- Proposal 01 (ensemble reviewer) — strongly recommended prerequisite for context efficiency. Could land in the other order, but the orchestrator's context budget is much tighter without it.
- Proposal 02 (stabilization fixes) — the autonomous-fix policy applies to the new orchestrator brief.
- Proposal 03 (plan batching) — independent. If batching lands first, fixer plans naturally inherit batch boundaries; if batching lands later, fixer plans use one-commit-per-step until then.

## Out of scope

- Parallel orchestration (Proposal 06).
- Local LLM backend for the orchestrator (Opus-only).
- Cross-task orchestration (one orchestrator managing multiple tasks). Far future.
