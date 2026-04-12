# Tasks

## [active] Gemini CLI support + ensemble reviewer
Add Gemini CLI as a backend in `spawn-agent.ps1` and wrap it in an ensemble pattern (N=3 parallel reviewers + 1 Opus handler) so review runs are noise-filtered, faster, and higher confidence than today's single-shot Sonnet reviewer. Output contract stays identical so callers don't need to know whether the reviewer is ensembled.

**Design doc:** [plugins/mill/doc/proposals/01-gemini-ensemble-reviewer.md](plugins/mill/doc/proposals/01-gemini-ensemble-reviewer.md)

## Stabilization fixes (autonomous-fix policy + worktree isolation + mill-spawn parser)
Three small surgical fixes that survive the dual-Opus rewrite and apply to any orchestrator design. (1) Autonomous-fix policy: when a spawned implementer/orchestrator fixes its own broken tools mid-run, the commit gets `[autonomous-fix]` prefix and the SHA is reported in the final JSON. (2) Worktree isolation: encode in the conversation/workflow skills that a session running from a child worktree never edits or commits in the parent (reads via `git -C` are fine). (3) `mill-spawn.ps1` parser: today it only extracts bullet-point lines as task description, so the new prose-paragraph tasks.md format produces empty handoff/status bodies. Rewrite the parser to capture prose paragraphs.

**Design doc:** [plugins/mill/doc/proposals/02-stabilization-fixes.md](plugins/mill/doc/proposals/02-stabilization-fixes.md)

## Plan-format batching (one commit per logical batch)
Introduce `### Batch N: <name>` grouping in the plan format so the implementer commits at batch boundaries instead of after every atomic step. Reduces commit noise (~18 commits per task → ~5) while preserving the atomicity invariant for clarity. Resume protocol on mid-batch crash: re-run the whole batch from the start (steps are idempotent).

**Design doc:** [plugins/mill/doc/proposals/03-plan-format-batching.md](plugins/mill/doc/proposals/03-plan-format-batching.md)

## Three-skill split (mill-start, mill-plan, mill-go) + pre-arm pattern
Split today's `mill-go` into `mill-plan` (P2: plan write + plan review) and `mill-go` (P3: implementation orchestration). Add a "pre-arm" wait mode to `mill-go` so the user can invoke it before P2 finishes — `mill-go` polls `status.md` every 30s until `phase: planned`, then spawns Thread B. Enables walking away after P1 and coming back to a finished task. `thread-b.lock` prevents race between two concurrent pre-armed sessions.

**Design doc:** [plugins/mill/doc/proposals/04-three-skill-split.md](plugins/mill/doc/proposals/04-three-skill-split.md)

## Dual-Opus orchestrator (Thread B = Opus)
Make `mill-go`'s Thread B an **Opus orchestrator** instead of today's Sonnet implementer-orchestrator. Opus stays the brain across both planning and execution: it spawns implementer/fixer subprocesses (Sonnet/Haiku, fresh per spawn), spawns reviewers (ensemble from Proposal 1), and applies the receiving-review decision tree itself. Code edits are always delegated to fresh subprocesses; design judgment is always Opus. Fixer plans are written by Thread B in the same plan-format as the original plan.

**Depends on:** Three-skill split (Proposal 4). Strongly benefits from Gemini ensemble (Proposal 1) being landed first.

**Design doc:** [plugins/mill/doc/proposals/05-dual-opus-orchestrator.md](plugins/mill/doc/proposals/05-dual-opus-orchestrator.md)

## Parallelizable batches
Extend the batching concept from Proposal 3 with a dependency DAG: identify which batches can be implemented in parallel (no shared files, no shared state) versus which must be serialized. Lowest priority — the gain may be marginal once the implementer subprocess is on Haiku, and the architecture cost is high (concurrent worktrees, merge-back, parallel crash recovery). Worth keeping on the list but should not be tackled until empirical data from real Haiku runs shows that wall-clock is still the bottleneck.

**Depends on:** Plan-format batching (Proposal 3) and dual-Opus orchestrator (Proposal 5).

**Design doc:** [plugins/mill/doc/proposals/06-parallelizable-batches.md](plugins/mill/doc/proposals/06-parallelizable-batches.md)
