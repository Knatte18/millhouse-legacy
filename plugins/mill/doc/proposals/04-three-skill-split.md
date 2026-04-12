# Proposal 04 — Three-Skill Split + Pre-Arm Pattern

**Status:** Proposed
**Depends on:** none
**Blocks:** Proposal 05 (dual-Opus orchestrator) builds on this split

## One-line summary

Split the current `mill-go` into two skills (`mill-plan` for P2 — plan write + plan review, and `mill-go` for P3 — implementation orchestration). Add a "pre-arm" wait pattern to `mill-go` so it can be invoked before P2 finishes and automatically picks up the run when the plan is ready.

## Background

### Today's structure

```
mill-start  →  P1 (interview, discussion.md)            owned by Thread A (Opus)
mill-go     →  P2 (plan + plan review)                   owned by Thread A (Opus)
            →  P3 (implementation orchestration)          spawns Thread B (Sonnet today)
            →  P4 (merge)                                 Thread B's last act
```

`mill-go` is a single skill that owns both plan writing and the spawn of the implementer-orchestrator. The user invokes `mill-go` once and it runs end-to-end if the session stays open.

### Why this is awkward

1. **Phase boundaries don't match skill boundaries.** P2 is a "thinking" phase (Opus writes the plan, Opus reviewers tear it apart). P3 is an "execution" phase (an orchestrator spawns implementers and reviewers). They have different runtime profiles, different failure modes, different resume protocols. Bundling them in one skill conflates concerns.

2. **No way to "pre-arm" P3.** If the user wants to run P2 in the morning and trigger P3 in the afternoon (or come back the next day to trigger it), they have no clean handoff. Today, you have to either (a) leave a `claude` session running for the whole day, or (b) come back at exactly the right moment to invoke `mill-go` for the spawn.

3. **Resume protocols are conflated.** mill-go has to handle "resume P2 from `phase: discussed` (no plan yet)", "resume P2 from `phase: discussed` (plan written but not approved)", "resume P2 from `phase: planned` (plan approved, P3 not yet started)", and several P3 resume cases. That's a lot of branches in one skill.

4. **Naming.** The current `mill-go` is named after its end-state action ("go implement"), but it actually does both the planning and the spawning. The name doesn't reflect what it actually does first.

### The split

```
mill-start  →  P1 (interview, discussion.md)             owned by Thread A (Opus)
mill-plan   →  P2 (plan + plan review)                   owned by Thread A (Opus)
mill-go     →  P3 (implementation orchestration)          spawns Thread B
            →  P4 (merge)                                 Thread B's last act
```

Three skills, three phases, three names that say what they do. Each skill owns one phase boundary and resumes from one set of states.

### The pre-arm pattern

Today: user runs `mill-go`, it does P2, it spawns Thread B, it monitors. User must be present at all phase boundaries.

New: user runs `mill-plan` (autonomous from end of P1), then runs `mill-go` whenever they want to trigger P3. If `mill-go` is invoked while `mill-plan` is still running, `mill-go` enters a **wait mode**: it polls `_millhouse/task/status.md` every 30 seconds and waits for `phase:` to reach `planned`. When that happens, it spawns Thread B and continues. If `mill-go` is invoked after `mill-plan` is done, it just spawns immediately. The user can pre-arm `mill-go` in the morning, walk away, and let the chain complete on its own.

## Goals

1. Create a new `mill-plan` skill that owns the P2 phase (plan write + plan review). Extract the relevant logic from today's `mill-go`.
2. Reduce `mill-go` to its P3 responsibility (spawn implementer-orchestrator, monitor, report).
3. Add a wait-mode entry path to `mill-go` that polls `status.md` for `phase: planned` (or beyond) before proceeding.
4. Add a `thread-b.lock` (or similar) mechanism so two concurrent `mill-go` pre-arm sessions can't race on the spawn.
5. Update `mill-start` to optionally spawn `mill-plan` as a background process at the end of P1, enabling the full autonomous chain.
6. Update resume protocols so each skill only handles its own phase's resume cases.
7. Encode the "Worktree isolation" rule from Proposal 02 into the new mill-go and mill-plan skills (no parent-side writes).

## Non-goals

- Changing the model of the implementer-orchestrator. This proposal keeps Thread B as Sonnet (today's behavior). Proposal 05 swaps it for Opus.
- Changing the plan format. Proposal 03 covers batching.
- Changing the reviewer. Proposal 01 covers the ensemble.
- Auto-spawning `mill-go` from `mill-plan`. Pre-arm is the user's choice — the chain stops at `phase: planned` until the user explicitly invokes `mill-go` (possibly long before the planned state is reached).

## Design decisions

### Decision: mill-plan is a separate skill, not a flag on mill-start or mill-go

**Why:** Skills are first-class user-facing commands. Users should be able to invoke `mill-plan` directly to resume from `phase: discussed`, without needing to remember a flag like `mill-start --finalize` or `mill-go --plan-only`. Three skills, three commands, three phases.

**Alternatives rejected:**
- `mill-start --finalize` (couples start and plan into one command, hides the phase boundary)
- `mill-go --plan-only` (counterintuitive — "go" implies action, not planning)
- A single `mill` command with subcommands (`mill start | plan | go`) — possible but adds an indirection layer the user has to learn

### Decision: mill-go's pre-arm wait mode is a foreground polling loop

When `mill-go` enters and finds `phase: discussed | discussing | planning`, it enters a wait loop:

```bash
TARGET="planned"
TIMEOUT_SECONDS=14400  # 4 hours, configurable
START=$(date +%s)
while true; do
  PHASE=$(awk '/^```yaml/{f=1;next} /^```/{f=0} f && /^phase:/{print $2}' _millhouse/task/status.md)
  case "$PHASE" in
    planned)
      echo "Plan ready, proceeding to spawn Thread B."
      break ;;
    blocked|complete)
      echo "Aborting: phase=$PHASE"
      exit 1 ;;
    implementing|testing|reviewing)
      echo "Already past planned, resuming."
      break ;;
    *)
      ELAPSED=$(( $(date +%s) - START ))
      if [ $ELAPSED -gt $TIMEOUT_SECONDS ]; then
        echo "Timeout waiting for plan after ${TIMEOUT_SECONDS}s"
        exit 2
      fi
      echo "Waiting for plan (phase=$PHASE, ${ELAPSED}s elapsed)..."
      sleep 30
      ;;
  esac
done
# Continue with normal mill-go P3 logic
```

**Why:** `mill-go` is doing nothing else while waiting, so a foreground polling loop is the simplest fit. It's a single skill invocation that blocks until ready. The user sees periodic "Waiting..." output so it doesn't feel hung.

**Alternatives rejected:**
- Use the `Monitor` tool — designed for parallel watching where the main thread does other work; here there's nothing parallel to do, so it's overkill.
- Use a hook on file change — adds infrastructure complexity for a simple polling case.
- inotify-style file watching — Windows compatibility issues, overkill.

### Decision: thread-b.lock prevents double-spawn

When `mill-go` is about to spawn Thread B (after wait-mode exits or on a fresh invocation that finds `phase: planned`), it claims a lock at `_millhouse/task/thread-b.lock` containing `pid`, `timestamp`, `branch`. If the lock already exists and the PID is alive, mill-go reports "Another mill-go session is starting Thread B (pid=N)" and exits cleanly. If the lock is stale (PID dead), it removes and re-acquires. Same pattern as `merge.lock` from `mill-merge`.

**Why:** A user can pre-arm two `mill-go` sessions by accident (one in their work IDE, one in a terminal), and both would try to spawn Thread B simultaneously. The lock prevents the race cleanly.

**Alternatives rejected:**
- Trust the user to only have one session (fragile).
- Atomic check-and-swap on `phase:` (workable but more complex than a lock file).

### Decision: mill-start optionally spawns mill-plan in the background

At the end of P1 (`phase: discussed`), `mill-start` asks: "Plan this now? Y/n". If yes, it invokes `mill-plan` as a background process via `Bash run_in_background: true` and exits immediately. The user can close the terminal; `mill-plan` runs autonomously.

**Why:** Most users will want to chain P1 → P2 immediately. The optional spawn handles the common case without forcing it.

**Alternatives rejected:**
- Always spawn (loses control — sometimes the user wants to take a break before P2).
- Never spawn (forces extra manual step).
- Inline P2 inside mill-start's session (long-running interactive session, can blow context).

### Decision: Worktree isolation is encoded in both mill-plan and mill-go

Both new skills explicitly reference Proposal 02's worktree-isolation rule and never `cd` into the parent worktree. Any operation that conceptually involves the parent uses `git -C <parent> ...` and is read-only.

The only legitimate parent-write skills are `mill-merge` and `mill-cleanup`, which the new `mill-go` invokes at end-of-run as today.

**Why:** Proposal 02 establishes the rule; this proposal applies it.

## The pre-arm user flow

Three example flows the new design enables:

### Flow A — All in one sitting

```
You: mill-start
  └─ Interview phase (P1), interactive
  └─ Phase: discussed
  └─ "Plan this now? Y/n" → Y
  └─ spawns mill-plan in background
  └─ exits

mill-plan (background, autonomous):
  └─ Phase: planning, Phase: planned
  └─ exits

You (still in same session): mill-go
  └─ Sees phase: planned
  └─ Spawns Thread B in background
  └─ Reports back to you, optionally blocks-and-monitors
```

### Flow B — Walk-away after P1

```
Morning, you: mill-start → P1 → "Plan this now?" → Y → mill-plan spawned → close terminal
[mill-plan runs autonomously, finishes after ~20 min]

Afternoon, you: open new session, mill-go
  └─ Sees phase: planned
  └─ Spawns Thread B
  └─ Reports back
```

### Flow C — Pre-arm before P2 finishes

```
Morning, you: mill-start → P1 → "Plan this now?" → Y → mill-plan spawned
You (in same session, immediately): mill-go
  └─ Sees phase: discussed (mill-plan still running)
  └─ Enters wait mode
  └─ Polls status.md every 30s
  └─ "Waiting for plan (phase=discussed, 30s elapsed)..."
You: walk away

[mill-plan finishes after 20 min, status.md becomes phase: planned]
[mill-go's wait loop detects it on next poll]
[mill-go spawns Thread B in background]
[Thread B runs to completion]
[Notification toast on your machine when done]
```

This is the killer use case. Pre-arm in the morning, walk away, come back to a finished task.

## Open questions for the discussion phase

1. **Default for the "Plan this now?" prompt** — Y or n? Y is more convenient for the common case but accidentally chains a lot of compute. Probably Y with a clear escape (Ctrl+C cancels mill-plan spawn).
2. **mill-go pre-arm timeout** — 4 hours feels right but is arbitrary. Configurable via `_millhouse/config.yaml` `runtime.pre-arm-timeout-seconds` with a sane default.
3. **Should `mill-plan` also pre-arm-wait?** I.e., if invoked while `phase: discussing`, should it wait for `discussed`? Probably yes for symmetry, but P1 is interactive so this is a less common case.
4. **What happens if the user invokes `mill-plan` twice?** Same race as `mill-go`. Need a `mill-plan.lock` too, or unify into one `task.lock` with a role field.
5. **mill-status display** — should it show "pre-armed mill-go waiting in PID N" so the user knows a session is parked?
6. **Resume after Ctrl+C in wait mode** — when the user kills a pre-armed mill-go before the plan is ready, should it leave any state? Probably no — wait mode has no side effects on disk, so killing it is safe.
7. **Naming again** — is `mill-plan` clearly the planner? Or does it sound like "make a plan to do mill operations"? Compare with `mill-write-plan` (longer but unambiguous). Probably `mill-plan` is fine; the verb-noun convention is clear from context.

## Acceptance criteria

- A user can invoke `mill-plan` from `phase: discussed` and it runs P2 to `phase: planned` autonomously, with no user interaction, identical output to today's `mill-go` P2 logic.
- A user can invoke `mill-go` from `phase: planned` and it spawns Thread B and runs P3 to completion (identical to today's `mill-go` P3 logic).
- A user can invoke `mill-go` from `phase: discussed` (or any pre-`planned` phase), and `mill-go` enters wait mode and polls every 30s until `phase: planned`, then spawns Thread B and proceeds.
- Two simultaneous `mill-go` pre-arm sessions: one acquires the spawn lock, the other reports "another session is starting Thread B" and exits cleanly.
- `mill-start` at end of P1 prompts "Plan this now?", spawns `mill-plan` in background on Y, exits cleanly.
- Resume after a crash mid-P2 lands in `mill-plan`'s resume protocol; resume mid-P3 lands in `mill-go`'s.
- Grep across the new skills shows zero `cd <parent>` patterns.

## Risks and mitigations

- **Wait mode hangs forever** if `phase:` somehow gets stuck without reaching `planned` or `blocked`. Mitigation: timeout at 4 hours by default, configurable.
- **mill-plan spawn from mill-start fails silently** because background spawns can't easily report errors back to the parent. Mitigation: mill-plan's first action is to write `phase: planning` to status.md. mill-start's last action is to verify the spawn happened by checking that field after a 5-second wait. If still `discussed`, report failure.
- **User confusion** — three skills instead of one is more to learn. Mitigation: clear docs, mill-status displays the next-action skill name explicitly ("Run mill-plan to start planning" / "Run mill-go to start implementation").
- **Resume protocol regressions** — extracting code from one skill into two creates an opportunity to lose a resume case. Mitigation: explicit test matrix of all phase × invocation-skill combinations during the implementation phase.

## Dependencies

- None for landing this proposal independently.
- Proposal 05 (dual-Opus orchestrator) builds on this split — it changes Thread B's model and brief, but the skill structure (mill-start / mill-plan / mill-go) stays the same.
- Proposal 02 (stabilization fixes) provides the worktree-isolation rule that this proposal applies.
