# Proposal 03 — mill-go v2: Three-Skill Split + DAG-Aware Executor

**Status:** Proposed
**Worktree:** W3 — ships as a v2 batch-plan (dogfood #1 of the format delivered by W2)
**Depends on:** W2 (plan-format v2 and planner must exist first)
**Blocks:** none

## One-line summary

Split today's monolithic `mill-go` into three skills (`mill-start` / `mill-plan` / `mill-go`) with a pre-arm wait pattern, rewrite `mill-go` as a DAG-aware layer-parallel executor where Thread A owns WHAT and Thread B owns HOW, add a subtask-decomposition heuristic to `mill-start` Phase: Discussion, and set Sonnet as the default implementer floor with Haiku out of the default pipeline.

## Why one worktree for all of this

Four sub-changes, one worktree. The reasoning:

- **The three-skill split and the executor rewrite touch the same skill files** (`mill-go`, `mill-start`, and the new `mill-plan`). Splitting them into separate worktrees means rewriting mill-go twice. Bundling avoids churn.
- **The subtask-decomposition heuristic lives in `mill-start` Phase: Discussion**, which this worktree is already restructuring. Fits naturally into the same set of edits.
- **The Sonnet-floor config default is trivial** (one config change + one note in mill-setup). Bundling it saves a round-trip commit/push/review cycle.

Shipping as a v2 batch-plan (produced by W2's `mill-plan` v2) makes W3 the first real consumer of the new format — the dogfood moment.

---

## Part A — Three-skill split + pre-arm pattern

### Today's structure

```
mill-start  →  P1 (interview, discussion.md)            owned by Thread A (Opus)
mill-go     →  P2 (plan + plan review)                   owned by Thread A (Opus)
            →  P3 (implementation orchestration)          spawns Thread B
            →  P4 (merge)                                 Thread B's last act
```

`mill-go` is one skill that owns plan writing, plan review, and the spawn of the implementer-orchestrator. Awkward because:

1. **Phase boundaries don't match skill boundaries.** P2 is thinking-heavy (Opus writes the plan, reviewers tear it apart). P3 is execution (orchestrator spawns implementers and reviewers). Different runtime profiles, different failure modes, different resume protocols.
2. **No way to "pre-arm" P3.** If the user wants to run P2 in the morning and trigger P3 in the afternoon, they either leave a session running all day or come back at exactly the right moment.
3. **Resume protocols are conflated.** mill-go has to handle P2 resume (several states) and P3 resume (several more states) in one skill.
4. **Naming.** `mill-go` is named after its end-state action ("go implement") but actually does both planning and execution.

### The new structure

```
mill-start  →  P1 (interview, discussion.md)             Thread A (Opus)
mill-plan   →  P2 (plan + plan review)                   Thread A (Opus)
mill-go     →  P3 (implementation orchestration)          Thread B (Opus in W3, was Sonnet)
            →  P4 (merge)                                 Thread B's last act
```

Three skills, three phases, three names that match what they do. Each skill owns one phase boundary and one set of resume states.

### Pre-arm wait mode

Today: user runs `mill-go`, it does P2, it spawns Thread B, it monitors. User must be present at every phase boundary.

New: user runs `mill-plan` (autonomous from end of P1), then runs `mill-go` whenever they want to trigger P3. If `mill-go` is invoked while `mill-plan` is still running, `mill-go` enters **wait mode** and polls `_millhouse/task/status.md` every 30 seconds for `phase: planned`. When that happens, it claims the spawn lock and starts. If `mill-go` is invoked after `mill-plan` is done, it starts immediately.

```bash
TARGET="planned"
TIMEOUT_SECONDS=14400   # 4 hours, configurable via runtime.pre-arm-timeout-seconds
START=$(date +%s)
while true; do
  PHASE=$(awk '/^```yaml/{f=1;next} /^```/{f=0} f && /^phase:/{print $2}' _millhouse/task/status.md)
  case "$PHASE" in
    planned)                                  echo "Plan ready, proceeding." ; break ;;
    blocked|complete)                         echo "Aborting: phase=$PHASE"   ; exit 1 ;;
    implementing|testing|reviewing)           echo "Past planned, resuming."   ; break ;;
    *)
      ELAPSED=$(( $(date +%s) - START ))
      [ $ELAPSED -gt $TIMEOUT_SECONDS ] && { echo "Timeout"; exit 2; }
      echo "Waiting for plan (phase=$PHASE, ${ELAPSED}s elapsed)..."
      sleep 30 ;;
  esac
done
```

Foreground polling loop. Simple, visible, cancellable with Ctrl+C, no persistent state (killing it is safe).

### `thread-b.lock` prevents double-spawn

Before spawning Thread B, `mill-go` claims a lock at `_millhouse/task/thread-b.lock` containing `pid`, `timestamp`, `branch`. If the lock already exists and the PID is alive, the second `mill-go` reports "Another mill-go session is starting Thread B (pid=N)" and exits cleanly. If the lock is stale (PID dead), it removes and re-acquires. Same pattern as `merge.lock` from `mill-merge`.

### Killer flow: pre-arm before P2 finishes

```
Morning: mill-start → P1 → "Plan this now? Y/n" → Y → mill-plan spawned → walk away
         mill-go (same session, immediately)
           → sees phase: discussed (mill-plan still running)
           → enters wait mode, polls every 30s
           → close terminal, walk away

[mill-plan finishes after ~20 min, status.md becomes phase: planned]
[mill-go's wait loop detects it on next poll]
[mill-go claims thread-b.lock and spawns Thread B]
[Thread B runs to completion]
[Notification toast when done]
```

One command in the morning, done by the end of the day with zero mid-day check-ins.

### `mill-start` optionally spawns `mill-plan` in the background

At the end of P1, `mill-start` asks "Plan this now? Y/n". On Y, it invokes `mill-plan` via `Bash run_in_background: true` and exits. The user can close the terminal; `mill-plan` runs autonomously. On n, the user is expected to invoke `mill-plan` manually later. Default: Y.

Rejected alternative: always auto-spawn. Sometimes the user wants to walk away before P2 — Y-as-default with Ctrl+C escape handles both cases.

### Worktree isolation

Both `mill-plan` and `mill-go` explicitly reference the worktree-isolation rule (W1 Fix 9) and never `cd` into the parent worktree. Any parent operation uses `git -C <parent>` and is read-only. Only `mill-merge` and `mill-cleanup` legitimately write parent state.

---

## Part B — mill-go v2 executor: DAG-aware, layer-parallel, Thread A owns WHAT, Thread B owns HOW

This is the largest piece of W3. Absorbs the former dual-Opus-orchestrator and parallelizable-batches proposals.

### The split

| Layer | Owns | Outputs |
|---|---|---|
| **Thread A (Opus, in `mill-plan`)** | The WHAT — which cards exist, what they contain, what they depend on | v2 plan directory with full card content AND explicit `depends-on:` / `touches-files:` annotations per card |
| **Thread B (Opus, in `mill-go`)** | The HOW — in what order and grouping to execute the cards | DAG + topological layer schedule + per-layer Sonnet sub-agent spawns + commit sequence + receiving-review loop |

**Thread B does NOT:**
- write fixer plans (the old dual-Opus design — removed);
- modify Thread A's cards (the plan is the design contract);
- silently merge cards to bypass a circular dependency (the millpy task saw Sonnet do this on Step 21 + Step 23; the correct response is to flag and escalate);
- guess at impossible states.

When Thread B discovers something Thread A's plan cannot support, it escalates back to Thread A for plan revision. "Impossible states" include circular dependencies in the DAG, missing referenced symbols, conflicting `touches-files:` sets that cannot be resolved by topological ordering.

### Execution flow

Replaces today's "Phase: Spawn Thread B" with a scheduler loop.

1. **Parse `_millhouse/task/plan/00-overview.md`** to get the batch list and batch-level dependency graph.
2. **Parse every batch file's step cards** to get per-card `depends-on:` and `touches-files:`.
3. **Build the DAG.** Nodes are step cards (globally numbered). Edges come from `depends-on:`. Additional implicit edges come from `touches-files:` overlap (two cards touching the same file must serialize, even if not declared).
4. **Topologically sort into layers.** Layer 0 = cards with no incoming edges. Layer N = cards whose only incoming edges point to cards in layers < N. Report the layer schedule to the user before starting.
5. **For each layer, sequentially:**
   a. Spawn one Sonnet sub-agent per card in the layer (parallel within the layer, capped by `config.execution.max-parallel-workers`).
   b. Each sub-agent receives `00-overview.md` + its card's batch file + the specific card. It reads the plan, writes its files, runs its intra-card TDD cycle if any, does NOT commit.
   c. Wait for all layer workers to return.
   d. Orchestrator runs `pytest <project>/` once for the whole worktree.
   e. **If green:** commit each card in topological order with its per-card commit message. Move to next layer.
   f. **If red:** parse pytest output, map failing tests to cards, spawn repair workers for just the failing cards with the test failure log. Re-run pytest. Repair loop caps at N attempts (default 3); on failure, halt and escalate.
6. **Phase: Completion** — same as v1 (final verification, status.md bump to `complete`, optional handoff to `mill-merge`).

### Why layer-parallel (not full-parallel + batch-test)

Full-parallel means spawn N workers at once, defer pytest to the very end. It works for fanout-heavy tasks (repo-wide renames, doc generation). It breaks on Python packages with internal imports — one file importing from another that doesn't exist yet causes import-error cascade during pytest collection.

During the millpy task, card 14 imported from card 13, card 21 imported from card 19, etc. Until the dependency chain was satisfied, pytest couldn't even LOAD the test files. The parallelism has to respect import-time dependencies, which means it has to respect layers. Layer-parallel + per-layer pytest is the sweet spot for tight-coupled Python packages; the speedup is capped at ~2x on tasks like millpy (the reviewer-chain critical path is the bottleneck), not the 5-7x one might hope for, but 2x is worth it.

Full-parallel is tracked as a potential v3 for fanout-heavy tasks where it would matter. Out of scope for W3.

### Receiving-review loop lives in Thread B

When a code-review round returns, Thread B:

1. Reads the (synthesized, if ensembled) code-review report.
2. Applies the `mill-receiving-review` decision tree per finding: VERIFY → HARM CHECK → FIX or PUSH BACK.
3. For FIX decisions: spawns a Sonnet repair worker per card affected, with the test-failure log or review finding as input. Same machinery as the repair loop in step 5f above.
4. For PUSH BACK decisions: cites the plan's `### Decision:` blocks as evidence in a response report. No fixer plan — just a structured reply to the reviewer.
5. Re-runs the reviewer with the response attached. Loops until APPROVE or until an impasse is reached, at which point Thread B escalates to Thread A.

**Thread B never writes fixer plans.** The old dual-Opus design had Thread B generate a small "fix plan" in the same plan-format for the fixer subprocess to read. Removed because:
- Sonnet repair workers can take a test-failure log + card reference directly — no intermediate plan required.
- Fixer plans were an extra round of bookkeeping for no clear gain.
- Keeping Thread B strictly in orchestrator role (read reports, decide, dispatch, never author content) clarifies the Thread A / Thread B split.

### Context budget for Thread B

Thread B is alive across all of P3. Back-of-envelope budget with ensemble reviewer (W2's Part C):

- Plan directory + discussion load at start: ~30k tokens
- Per code-review round: ~5k tokens (synthesized combined report from the handler)
- Per repair dispatch: ~3k tokens (pytest output + card reference)
- Status.md polling: negligible

With 3 review rounds × 3 repairs each: ~30k + 15k + 27k = ~72k tokens of active context. Well within Opus's budget.

Without ensemble: ~90k tokens. Still workable but tighter. Ensemble is a strong practical prerequisite.

### Config

```yaml
models:
  orchestrator: opus       # was sonnet for Thread B
  implementer: sonnet      # floor per Part D below; no haiku in default pipeline
  fixer: sonnet            # same model as implementer, different input

execution:
  max-parallel-workers: 4  # cap per layer
  repair-attempts: 3       # cap before escalating
  pre-arm-timeout-seconds: 14400
```

---

## Part C — Independence-signal check in `mill-start` Phase: Discussion

Earlier drafts of this part proposed a size-based heuristic: "≥25 cards or ≥4 concern areas triggers a split prompt". That trigger is largely obsolete once W2 (batch-plan directories, per-batch review, ensemble plan-review) and Part B (layer-parallel executor) are in place. Size stops being the painful axis — reviewer budget, wall-clock, and cognitive load are all addressed structurally. A size-based prompt would fire false positives on exactly the kind of task it was meant to help (monolithic deliveries that legitimately need to stay one worktree).

**What is left as a genuine reason to split:** independence, not size. Three qualitative signals, any one of which is a strong hint:

1. **Different merge schedules.** Sub-task A has to ship now; sub-task B can wait. Different stakeholders, different ship dates, different release trains.
2. **Cross-repo boundaries.** One part of the work belongs in `millhouse`, another part in an external repo, and they cannot physically co-exist in one worktree.
3. **Scope-level rollback granularity.** The user wants to be able to revert "feature X" as a unit without losing "feature Y". Per-card commits alone are not enough — what's needed is a branch boundary.

None of these correlate with card count. They are qualitative signals Thread A recognizes from the discussion, not counts Thread A adds up.

### The check

At the end of Phase: Discussion, before transitioning to Phase: Plan, Thread A asks itself: **"Is there any reason the pieces we just discussed cannot all ship as one merge?"** It walks the three signals above against the discussion content and, only if at least one fires, prompts the user:

> The discussion touches pieces that look like they might be independent:
>
> - [concrete signal from the discussion, e.g., "the CI cleanup could ship next week while the API rewrite takes a month"]
>
> Would you like to:
> 1. Keep this as one task (v2 batch-plan format will handle the size)
> 2. Split into sub-tasks I propose: [A, B, C]
> 3. Propose your own split
>
> (Default: option 1. Only choose option 2 or 3 if the pieces genuinely need to ship at different times, cross repo boundaries, or need independent rollback.)

If no signal fires, **no prompt**. The default — one task, v2 batching — goes through silently. This is deliberate: millpy was the kind of task where the old size-based trigger would have fired, and the right answer was still "monolith + batching". Avoiding the false positive is worth more than catching every edge case.

### Not a hard stop

Even when the check fires, option 1 (monolith with batching) stays on the table and is the recommended default for any task where the user is unsure. Splitting costs planning overhead (per-task ceremony, per-task review rounds) and loses dependency visibility across sub-tasks. Choose it only when the independence signal is strong.

### Motivation

Section 5f of the millpy retrospective: "For millpy, separate worktrees are overkill because it is ONE logical delivery. Section 5e (batched plan in one worktree) is the right answer, not separate worktrees." The original size-based heuristic contradicted this conclusion — it would have nudged the user toward splitting a task that the retrospective itself said should have stayed whole. Reframing the check around independence signals aligns it with the retrospective's actual recommendation.

---

## Part D — Config default: Sonnet as implementer floor; no Haiku in default pipeline

Small but important.

Set `models.implementer: sonnet` and `models.orchestrator: opus` as defaults in `_millhouse/config.yaml` and in `plugins/mill/skills/mill-setup` Step 4. Remove every Haiku reference from the default model slots.

**Reasoning.** During the millpy task, Sonnet made four correct judgement calls during implementation that Haiku would likely have botched:

1. **Test-vs-code failure triage.** When pytest failed, Sonnet correctly identified whether the bug was in the implementation or in the test, and fixed the right one.
2. **Circular import avoidance.** When Step 21 and Step 23 had a latent circular import concern, Sonnet flagged it (even if the resolution — silently merging the cards — was wrong; that's Thread B's escalation responsibility in Part B above).
3. **Spec-vs-reality reconciliation.** Sonnet caught places where `_parse_yaml_mapping` needed to be recursive because the actual config shape differed from the plan's assumption.
4. **`git mv` workaround.** When a file move caused a test-collection issue, Sonnet found the right git command to apply.

Haiku remains available as an explicit opt-in for bulk-fanout tasks (repo-wide renames, doc generation, many-small-file ports) where judgment is not required. It is not in the default pipeline.

Document the reasoning in the config file comments so future mill-setup re-seeds preserve it.

---

## Part E — `[autonomous-fix]` commit prefix policy for spawned subprocesses

Moved here from the earlier stabilization bundle because W3 rewrites the entire orchestrator brief. Patching today's Sonnet-orchestrator brief in an earlier worktree only to delete-and-rewrite it here would be wasted work.

### What happened

During the 2026-04-13 track-child-worktree run, the Sonnet implementer-orchestrator made two out-of-plan code commits to fix bugs in `spawn-agent.ps1` that were blocking its own work. Both fixes were correct and useful — without them the run would have stalled and required manual intervention. But there was no record of the reasoning, no automated way to find them in git log, and no scrutiny dedicated to those specific commits beyond their inclusion in the round-1 reviewer's whole-diff scan.

### Risk profile of "fix-and-continue"

- Surface-tested once — edge cases (empty stdout, error stdout, multi-line stdout) were not revalidated.
- Bypasses dedicated code review — the fix was reviewed as one line in a larger diff, not the scrutiny a standalone fix to a critical script deserves.
- No paper trail of reasoning — symptom, hypothesis, fix description not recorded.
- Spiral risk — "I fixed the tool, now its caller was also wrong, so I fixed that too" is the path to runaway scope expansion.
- Hides the underlying bug — block-and-surface forces visibility; fix-and-continue silently absorbs the problem.

The goal is not to ban autonomous fixes — blocking on every transient issue would force manual intervention on every run. The goal is to make them **visible** and **bounded**.

### The fix (minimum version)

1. **Mandatory commit tagging.** Out-of-plan tool fixes get an `[autonomous-fix]` prefix in the commit subject. Easy to grep, easy to spot in logs.
2. **Final JSON includes `autonomous_fixes: ["sha1", "sha2", ...]`.** When Thread B exits with `phase: complete`, its final JSON line reports the SHAs of any autonomous fixes made during the run. The user (or the completion notification) sees them in the report and can decide to keep, revert, or expand on them.

Start with the minimum. If a real out-of-plan fix later bites the user, escalate to the stronger version: per-fix justification file, hard cap (max 1 per run), explicit scope limit (only scripts Thread B is actively invoking).

### Scope

- The **new orchestrator brief** written as part of Part B gets the policy baked in from day one. No retrofit against the old brief — that brief is being replaced anyway.
- The **fresh-spawn implementer subprocess** (Sonnet, one-shot per card from Part B's DAG executor) does NOT get autonomous-fix permission. It is purely mechanical execution. Only the long-running Opus orchestrator can authorize fixes to its own tools.
- The **receiving-review decision tree** in Part B recognizes `[autonomous-fix]`-prefixed commits as legitimate out-of-plan changes when it is classifying findings.

### Acceptance

- The new orchestrator brief (Part B) has a section explaining when autonomous fixes are allowed and the tagging requirement.
- A test run that triggers an autonomous fix (e.g. by injecting a known-broken wrapper the orchestrator must work around) produces a commit with `[autonomous-fix]` in the subject and a final JSON line containing that commit's SHA.
- The receiving-review decision tree correctly classifies an autonomous-fix commit as in-scope when it is reviewed alongside the plan's normal commits.

---

## Non-goals

- **Full-parallel + batch-test execution mode.** Layer-parallel is enough for tight-coupled Python tasks. Full-parallel is a future v3 concern for fanout-heavy tasks.
- **Cross-task orchestration.** One orchestrator managing multiple tasks simultaneously. Out of scope.
- **Distributed orchestration across machines.** The `thread-b.lock` and `git pull --ff-only` guards handle the multi-machine race case correctly (abort-and-resolve), but distributed execution is not built.
- **Eliminating the long-running orchestrator.** A serverless / no-long-thread design is possible but a much larger rewrite with no clear win over Thread B staying warm.
- **Auto-spawning `mill-go` from `mill-plan`.** Pre-arm is the user's explicit choice. The chain stops at `phase: planned` until the user invokes `mill-go`.

## Dependencies

- **W2 is a hard prerequisite.** The executor reads v2 plan directories and per-card `depends-on:` metadata. Both come from W2.
- **W1 is a strong practical prerequisite.** The stabilization bundle unblocks real-world testing and adds the worktree-isolation rule this proposal references.
- **Ensemble reviewer is a strong practical prerequisite for Thread B's context budget.** Already landed with the Python toolkit; nothing new needed in W3.

## Risks and mitigations

- **Cost surprise from Opus as Thread B.** Idle Opus context across a multi-hour run could be expensive even when active token use is low. Mitigation: pilot on a small task first, measure, tune extended-thinking usage, set a hard ceiling on orchestrator session duration via `runtime.pre-arm-timeout-seconds`.
- **Layer-parallel coordination bugs are harder to debug than serial.** Mitigation: extensive logging of layer boundaries, per-card commit ordering, and repair dispatches. A "fall back to serial" escape hatch (`execution.max-parallel-workers: 1`) on any anomaly.
- **Cross-batch interface drift** in the receiving-review loop. Thread B might accept a reviewer finding that conflicts with a `### Decision:` in a different batch. Mitigation: the decision tree's HARM CHECK step requires Thread B to cite the plan section before accepting a FIX; missing citations mean the finding has to be verified manually.
- **Independence-signal check misses a genuine split case.** Qualitative signals are less mechanical than a card count — Thread A might miss that two pieces have different ship schedules. Mitigation: the signals (merge schedule, cross-repo, independent rollback) are listed explicitly in the check; if Thread A is unsure, it asks the user in Phase: Discussion directly ("does any of this need to ship separately?"). A false negative is recoverable — the user can always split manually by abandoning and re-starting. A false positive (the old size-based trigger) is not — the user loses confidence in the prompt and dismisses it reflexively.
- **Resume protocol regressions.** Splitting one skill into three creates opportunities to lose a resume case. Mitigation: explicit test matrix of all phase × invocation-skill combinations during implementation.

## Acceptance criteria

- **Part A.** A user can invoke `mill-plan` from `phase: discussed` and it runs P2 autonomously. A user can invoke `mill-go` from `phase: planned` and it spawns Thread B. A user can invoke `mill-go` from any pre-planned phase and it enters wait mode. Two simultaneous pre-armed `mill-go` sessions: one claims the lock, the other exits cleanly. `mill-start` at end of P1 prompts "Plan this now?", spawns `mill-plan` in background on Y.
- **Part B.** A v2 plan with declared `depends-on:` edges runs through the DAG builder and produces a correct topological layer schedule. Layer-parallel execution produces identical final code state to serial execution. Per-layer pytest catches failures at the right layer. Repair loop fixes a single-card failure without re-running unaffected cards. Thread B escalates to Thread A on circular-dependency detection. A reviewer finding that contradicts a documented `### Decision:` results in PUSH BACK, not silent FIX.
- **Part C.** A discussion containing an independence signal (e.g., "the CI cleanup ships this week, the API rewrite takes a month") produces the split prompt with the concrete signal quoted back. A discussion without any independence signal — regardless of card count — does not produce the prompt; the task proceeds silently to Phase: Plan with the v2 batch-plan default.
- **Part D.** Fresh `mill-setup` produces a config with `models.implementer: sonnet` and no Haiku references. Config file comments explain why.
- **Part E.** The new orchestrator brief has a section on autonomous-fix tagging. A test run that triggers an autonomous fix produces a commit with `[autonomous-fix]` in the subject and the SHA in the final JSON. The receiving-review tree classifies autonomous-fix commits as in-scope.

## Dogfood note

W3 ships as a v2 batch-plan written by W2's `mill-plan`. The plan directory will have batches for A (skill restructure), B (executor — probably split into DAG-builder, layer-spawner, per-layer-pytest, repair-loop sub-batches), C (independence-signal check), D (config default). This is the first time a non-trivial task uses the new format end-to-end; bugs discovered during W3's own implementation feed back into W2 fixes.
