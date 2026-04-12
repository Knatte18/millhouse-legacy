# Proposal 06 — Parallelizable Batches

**Status:** Proposed (lowest priority)
**Depends on:** Proposal 03 (plan-format batching), Proposal 05 (dual-Opus orchestrator)
**Blocks:** none

## One-line summary

Extend the batching concept from Proposal 03 with a dependency DAG: identify which batches can be implemented **in parallel** (no shared files, no shared state) versus which must be serialized. The orchestrator spawns multiple fixer subprocesses for the parallel batches, waits for them all, and advances through the DAG.

## Background

Many tasks have batches that touch entirely independent file sets. For example, the previous "track child worktree status" task had:

- Batch: update mill-spawn.ps1
- Batch: update mill-start
- Batch: update mill-merge
- Batch: update mill-abandon
- Batch: update mill-cleanup
- ...

Several of these are independent — they touch different skill files, with no cross-dependencies during execution. Today, they run sequentially because the implementer is a single subprocess. If they ran in parallel, the wall-clock time of the implementation phase could drop significantly.

This is a **performance optimization**, not a correctness improvement. It only makes sense after the foundations (Proposals 03 and 05) are in place, and it adds significant complexity. Hence the lowest priority.

## Why it's hard

1. **Dependency analysis.** The plan must declare which batches depend on which, or the planner must analyze the plan and infer dependencies (fragile). Explicit declaration is more reliable but adds plan-author burden.
2. **Concurrent git state.** Multiple subprocess implementers writing to the same working tree at the same time will corrupt the index. Each parallel batch needs its own working tree (a temporary git worktree per batch?) or its own staging area.
3. **Merging back.** After parallel batches finish, their commits need to be merged into a single linear history. The orchestrator has to resolve any incidental conflicts (even if the batches were declared independent, line numbers in shared metadata files like CLAUDE.md or version files can collide).
4. **Code review across parallel branches.** Does the reviewer see all parallel branches separately? Or merged? Or a synthesis of both? Each option has tradeoffs.
5. **Crash recovery in parallel mode.** If 2 of 4 parallel implementers crash, what's the recovery? Re-spawn just the failed ones? Re-do everything? How is partial progress detected?
6. **Resource contention.** Multiple Sonnet/Haiku subprocesses + ensemble reviewers + orchestrator all running simultaneously can hit API rate limits, local CPU saturation, etc. Backoff and throttling become necessary.

## Open questions for the discussion phase

(These are deliberately deep questions because this proposal is intentionally deferred — the answers feed into whether this proposal is even worth pursuing.)

1. **How parallelizable are real plans?** Need empirical data. Take the past N tasks (say, last 5) and analyze: what fraction of their batches were truly independent vs. serially dependent? If the answer is "mostly serial", this proposal is wasted effort.
2. **What does the dependency DAG look like in `plan.md`?** Options:
   - `### Batch 3: skill rewrites [depends-on: batch-1, batch-2]`
   - A separate `## Dependencies` section at the top of the plan: `batch-3 -> batch-1, batch-2`
   - YAML frontmatter on each batch: `dependencies: [batch-1, batch-2]`
3. **Concurrent worktree strategy.** Each parallel batch in its own ephemeral git worktree, merged back at the end? Or shared worktree with file-locking? The worktree-per-batch approach is cleaner but expensive in disk I/O.
4. **Code review strategy.** Three options:
   - **Per-batch review:** each parallel batch is reviewed independently before merging. Adds review overhead but catches issues in the smallest scope.
   - **Post-merge review:** all parallel batches merge first, then one review. Simpler but loses parallelism benefit during review (review sees the whole diff).
   - **Hybrid:** per-batch quick review (single-shot, fast), then post-merge thorough review (ensemble). Most complex but probably best.
5. **Merge order.** When parallel batches finish at different times, merge as they complete or wait for all? Probably wait — incremental merges complicate conflict resolution.
6. **Maximum parallelism.** What's a sensible cap? 3? 5? Configurable per task? Per machine?
7. **Failure handling.** If 1 of 4 parallel batches blocks, what happens to the other 3? Continue running them and surface the block, or kill them all?
8. **Cost.** N parallel implementers = Nx the cost per round (modulo synthesis savings). For large tasks this could be significant. Worth it?
9. **Does this break the implementer's atomicity invariant?** The plan-format says "each step card is independently implementable". For parallel batches, that's already true at the step level. But the **batches** also need to be independently implementable in parallel — which is a stronger claim. Need to formalize.
10. **Is this premature optimization?** Most tasks complete in under an hour. Saving 20 minutes of wall-clock at the cost of significant architecture complexity may not be worth it for the typical case.

## Goals (if and when this is built)

1. Define a dependency DAG syntax in `plan-format.md`.
2. Implement parallel orchestration in the new dual-Opus orchestrator (Thread B from Proposal 05): spawn multiple implementer/fixer subprocesses in parallel, manage their working trees, merge results.
3. Implement code-review strategy (likely per-batch quick review + post-merge ensemble review).
4. Implement crash recovery for parallel runs.
5. Add throttling / rate-limit handling for parallel API usage.
6. Add a simple analyzer to suggest batch parallelism opportunities during planning ("batch 3 and batch 4 modify disjoint file sets — consider marking them parallel").

## Non-goals

- Cross-task parallelism (multiple separate tasks running simultaneously). Different problem.
- Speculative execution. Different problem.
- Distributed orchestration (parallel batches on different machines). Way out of scope.

## Acceptance criteria

(Deliberately abstract until the design phase resolves the open questions above.)

- A plan with marked-parallel batches runs them in parallel and produces the same final code state as a sequential run.
- Wall-clock improvement of ≥30% on a task with ≥3 parallelizable batches.
- Crash recovery works: kill one of N parallel implementers, recover by re-spawning that one only.
- Code review catches the same issues whether batches ran in parallel or serially (no false negatives from the parallelism).

## Risks and mitigations

- **Premature optimization** — see open question 10. Mitigation: do the empirical study first. If most plans don't have parallel structure, abandon this proposal.
- **Architecture complexity outweighs gains.** Mitigation: hard time-box the implementation. If the design phase reveals it'll take >2 weeks of work for <2x speedup, defer further.
- **Bugs in parallel coordination are 10x harder to debug than serial bugs.** Mitigation: extensive testing, observability, and a "fall back to serial" escape hatch on any anomaly.

## Dependencies

- Proposal 03 (plan-format batching) — must land first; this proposal extends it.
- Proposal 05 (dual-Opus orchestrator) — must land first; the parallel orchestration is significantly easier with the orchestrator/implementer split in place.
- Proposal 01 (ensemble reviewer) — not strictly required, but the per-batch review strategy benefits from it.

## Why this is the lowest priority

1. **Optional improvement, not a correctness fix.** Mill works fine sequentially.
2. **High complexity-to-benefit ratio.** Significant architecture work for a wall-clock improvement that may or may not materialize in practice.
3. **Empirical question is unresolved.** We don't know yet whether real plans are parallelizable enough to be worth optimizing.
4. **Builds on multiple other proposals.** Can't even start before Proposal 03 and Proposal 05 are landed and stable.
5. **High risk of subtle bugs** that take a long time to find and fix.

Tackle the smaller, higher-leverage proposals first. Come back to this only after the foundations are solid and there's evidence that real-world plans would benefit.
