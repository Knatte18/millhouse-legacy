# Tasks

## [active] Python toolkit — retire PowerShell scripts (land first)
Retire the `.ps1` scripts in `plugins/mill/scripts/` in favor of a small, flat Python package (`millpy/` or similar — name settled in the discussion phase). Motivated by (a) the two `[autonomous-fix]` commits in the track-child-worktree run, both PowerShell-specific JSON/string quirks, (b) growing complexity of the scripts as Mill gains features, (c) the existing `spawn_reviewer.py` precedent showing the pattern works, (d) a bundled fix for `mill-terminal.ps1` / `mill-vscode.ps1` which currently open the new terminal / VSCode window in the repo root instead of the task's worktree cwd, and (e) providing the git-agnostic file-list bulker primitive (`bulk_payload.py`) that Proposal 02 Fix G needs — so that review rounds never again force throwaway WIP commits just to satisfy a `git diff`-driven payload. Migration order: `mill-spawn` → `mill-terminal` / `mill-vscode` → `fetch-issues` → `mill-worktree` → `spawn-agent` (highest risk, last). Hard non-goal: do **not** regenerate a 1.5x-sized test suite per module — test only pure logic (parsers, templates, path resolution, bulker), skip subprocess/filesystem wrappers, keep test LOC ≤ 0.5x script LOC. Absorbs Proposal 02 Fix C (mill-spawn.ps1 prose parser) — no separate PS1 patch needed. Provides the primitive half of Proposal 02 Fix G.

**Design doc:** [plugins/mill/doc/proposals/07-python-toolkit.md](plugins/mill/doc/proposals/07-python-toolkit.md)

## Stabilization fixes (bundled bug fixes from the gemini-cli-support run)
Bundled surgical fixes surfacing from recent autonomous runs. All survive the dual-Opus rewrite and apply to any orchestrator design. (A) Autonomous-fix policy: when a spawned implementer/orchestrator fixes its own broken tools mid-run, the commit gets `[autonomous-fix]` prefix and the SHA is reported in the final JSON. (B) Worktree isolation: encode in the conversation/workflow skills that a session running from a child worktree never edits or commits in the parent (reads via `git -C` are fine). (C) **Priority bug:** Thread B stops updating `status.md` after early steps — phase transitions and step boundaries lost, breaking the orchestrator→operator contract. (D) `spawn_reviewer.dispatch_workers` leaks empty timestamped dirs at repo root during tests because validation runs after `os.makedirs`. (E) code-reviewer subagent fabricates timestamps instead of running `date -u`; fix by having the orchestrator pre-compute `<REVIEW_FILE_PATH>` and substitute it into the materialized prompt. (F) Reviewer bulk payload must be driven by an **explicit file list**, never by `git diff` — solves both the "reviewer guesses at referenced-but-not-rewritten code" case and the "throwaway WIP commit to make the reviewer see the files" smell. The plan grows a `Read:` / `Files:` section; the orchestrator passes that list to a git-agnostic bulker primitive provided by Proposal 07. (Original Fix C — `mill-spawn.ps1` prose parser — moved to Proposal 07 since it's natively solved by the Python rewrite.)

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
