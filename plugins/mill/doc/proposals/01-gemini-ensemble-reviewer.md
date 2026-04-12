# Proposal 01 — Gemini CLI Support + Ensemble Reviewer

**Status:** Proposed
**Depends on:** none
**Blocks:** Proposal 05 (dual-Opus orchestrator) benefits significantly from this but is not strictly blocked

## One-line summary

Add Gemini CLI as a backend in `spawn-agent.ps1`, and wrap it in an ensemble pattern (N parallel reviewers + 1 Opus handler) so review runs are noise-filtered, faster, and higher confidence than today's single-shot Sonnet reviewer.

## Background

### Why ensemble at all

LLM reviewers are non-deterministic. Three sequential runs of the same review prompt against the same diff produce different findings — sometimes substantially different. A single-shot review is therefore unreliable: a finding that appears once may be a hallucination, and a real bug may be missed in the one run you happen to do.

The user has tested this empirically with Gemini 3 Pro (paid), Gemini Flash (free), and several local models (Qwen, GLM-4.7 Flash, DeepSeek) via Ollama and vLLM. Conclusion: GLM-4.7 Flash is fast and good for code review on a local 5090 GPU. Gemini 3 Pro is the cloud option of choice. Both are non-deterministic.

The standard fix for stochastic models is **ensemble**: run the same task N times in parallel, then synthesize. Findings that appear in ≥2/N runs are signal; singletons are noise.

### Why Gemini specifically

- **Different model family = different blind spots.** Sonnet-implementer + Sonnet-reviewer reviews itself in essence. Gemini brings independent training-distribution biases — it catches things Sonnet's training makes invisible to Sonnet.
- **Gemini 3 Pro is faster than Sonnet** for this task class. Even with 3 parallel calls + a synthesis step, total wall-clock beats single-shot Sonnet.
- **Cost.** Gemini 3 Pro per-token cost is competitive. 3 parallel + 1 synthesis is comparable to one Sonnet run.

### Why the handler is Opus, not Gemini

The ensemble's synthesis step is a **judgment task**: which findings appear in ≥2 reports? are they referring to the same code location with different wording? does each cited finding actually correspond to real code in the diff (verification against hallucination)? does any finding contradict a documented design decision (early HARM CHECK)?

A Gemini handler can do the structural merge. An Opus handler can additionally apply part of the receiving-review tree at synthesis time, pre-filtering hallucinated findings and pre-flagging design-conflict findings. That's a meaningful quality lift, and the cost is bounded (~$0.50–1.00 per round, ≤3 rounds per task).

Keeping the handler as Opus also preserves the architecture invariant from Proposal 05: **Opus is always the brain.** A Gemini handler would be a leak in that abstraction — judgment delegated to a non-Opus model in one specific spot.

### Why the handler is a separate spawn, not Thread B itself

If Thread B (the orchestrator) does the synthesis in its own context, every review round dumps ~30k tokens of raw reports into Thread B's working memory. By round 3 of a multi-round task, Thread B's context is polluted with ~100k tokens of mostly-filtered-out hallucinations. Thread B's judgment quality degrades as the run progresses.

A separate handler spawn pays the bloat cost in a disposable thread that gets thrown away after each round. Thread B only ever sees the synthesized ~5k-token combined report. Thread B's context stays lean across all rounds.

## Goals

1. Add a `gemini` backend to `spawn-agent.ps1` that routes `-ProviderName gemini` (or specific names like `gemini-3-pro`, `gemini-flash`) to the Gemini CLI, capturing stdout, parsing the JSON line, returning it in the same shape the existing claude backend uses.
2. Add a `glm` (or `local`) backend for local-LLM use via Ollama/vLLM HTTP. Optional — can be deferred.
3. Add a concurrent fan-out mechanism: spawn N reviewers in parallel, wait for all to finish, return the N report file paths to the handler. Either as a new `-Concurrency N` flag on `spawn-agent.ps1` or as a separate wrapper script `spawn-ensemble.ps1` that calls `spawn-agent.ps1` N times.
4. Implement the handler-Opus prompt that takes N raw reports + the original diff + the plan file as inputs, and produces a single combined report in the existing reviewer-output format.
5. Plumb the ensemble into the existing reviewer interface so callers (mill-go, mill-plan) don't need to know whether the reviewer is single-shot or ensembled — they invoke the same skill, get back the same JSON contract.
6. Per-ensemble subdirectories under `_millhouse/scratch/reviews/<ts>/` containing `r1.md`, `r2.md`, `r3.md`, `combined.md` for debuggability when synthesis goes wrong.

## Non-goals

- This proposal does NOT change the orchestrator. Today's Thread B (Sonnet implementer-orchestrator) keeps working with the new ensemble reviewer plumbed in. Proposal 05 does the orchestrator change.
- This proposal does NOT add multi-vendor model resolution config beyond what's already in `models.code-review` and `models.plan-review`. New `gemini-*` and `glm-*` model names just become valid values for those slots.
- This proposal does NOT touch the discussion-review or plan-review flow yet — it can, but the smallest useful version targets code-review only first, since code-review is where the wall-clock hurts most.

## Design decisions

### Decision: 3 reviewers in the ensemble (N=3) by default

**Why:** N=3 is the smallest N where majority voting is meaningful (2-of-3 = signal). N=5 would be more robust but costs more and the marginal value past N=3 is small. Configurable via `models.code-review.ensemble-size: 3` in `_millhouse/config.yaml` for users who want different N.

**Alternatives rejected:** N=2 (no majority possible — ties everywhere). N=5+ (cost grows linearly, marginal quality lift small). Variable N based on diff size (complexity, no clear win).

### Decision: Handler is Opus

See "Why the handler is Opus" above.

**Alternatives rejected:** Gemini handler (cheaper but breaks the "Opus is the brain" invariant and weaker at HARM CHECK). Sonnet handler (intermediate cost, intermediate value, no clear win over Opus).

### Decision: Handler is a separate spawn, not Thread B itself

See "Why the handler is a separate spawn" above.

**Alternatives rejected:** Thread B as handler (context bloat — ~30k tokens per round into Thread B's working memory).

### Decision: Output contract stays identical

The ensemble's final synthesized report uses the same JSON line + review file format as today's single-shot reviewer:

```json
{"verdict": "APPROVE" | "REQUEST_CHANGES", "review_file": "<absolute-path-to-combined.md>"}
```

**Why:** Callers (mill-go, mill-plan, the brief) don't need to know whether the reviewer is ensembled. Clean abstraction boundary. Drop-in replacement.

**Alternatives rejected:** A new "ensemble" output schema with per-finding confidence scores (more useful but couples the orchestrator to the ensemble shape).

### Decision: Disagreement resolution

- **Verdict:** majority wins. 2-of-3 REQUEST_CHANGES → REQUEST_CHANGES. All-3 APPROVE → APPROVE.
- **Findings:** include any finding cited by ≥2/N reviewers (deduped/normalized by the handler). Findings cited by only 1/N go into a "low-confidence" section the receiving thread can deprioritize or ignore.
- **Edge case — all 3 disagree completely:** signal that the diff is structurally confusing or the reviewers are running off different mental models. Handler flags it in the combined report; orchestrator can choose to re-run with a stricter prompt or escalate to user.

**Why:** Conservative (any flagged finding deserves attention) but noise-filtered (singletons are demoted, not dropped, so a real-but-rare finding can still surface for the orchestrator's review).

### Decision: Failure tolerance

- **≥2 of N succeed:** synthesize from the surviving reports. Note in the combined report that ensemble was N=2, not N=3, so the orchestrator knows the ensemble was degraded.
- **<2 of N succeed:** retry the failed ones once. If still <2, fall back to single-shot mode with a warning in the combined report, OR block — configurable via `models.code-review.failure-mode: degraded | block`.

**Why:** Don't pretend N=3 succeeded when one died — the ensemble math depends on knowing the actual N. Also don't kill the run for one transient failure.

## Open questions for the discussion phase

1. Should the ensemble apply to plan-review too, or just code-review? Plan-review reads a single document, not a diff — does the ensemble pattern even help there? Probably yes (non-determinism affects plan critique too), but lower priority and doesn't have to ship in the same task.
2. Local LLM backend (GLM-4.7 via Ollama/vLLM) — included in scope, or deferred to its own task? Probably deferred — Gemini cloud is the immediate need, local is a secondary "I want to run reviews on a long-haul flight" use case.
3. Concurrent spawn implementation: extend `spawn-agent.ps1` with `-Concurrency N`, or build a new `spawn-ensemble.ps1` wrapper that shells out N times? The wrapper is conceptually cleaner but adds another script to maintain.
4. Should the handler also apply the receiving-review decision tree (FIX/PUSH-BACK suggestions per finding), or just merge/dedupe? Merging is simpler and uncontroversial. Adding decision-tree application moves more work from Thread B to the handler — appealing but expands handler scope. Probably do merge-only first, add decision-tree later if it proves valuable.
5. How to express ensemble configuration in `_millhouse/config.yaml`? Probably:
   ```yaml
   models:
     code-review:
       default: gemini-3-pro
       ensemble-size: 3
       handler: opus
       failure-mode: degraded
   ```
6. What is the contract between the handler and downstream consumers when a finding is "low-confidence"? A separate `## Low-Confidence Findings` section in `combined.md` that Thread B is expected to skim but not act on automatically?

## Acceptance criteria

- `spawn-agent.ps1` accepts `-ProviderName gemini-3-pro` and successfully invokes the Gemini CLI, parsing its output and returning the standard JSON contract.
- A new ensemble entry point (script or skill) takes a reviewer prompt + diff + plan file, spawns N=3 reviewers in parallel, waits for all, invokes the handler-Opus, writes a combined report, and returns the standard JSON line.
- `mill-go`'s code-review phase can be configured to use the ensemble reviewer via `_millhouse/config.yaml` and works end-to-end on a real task.
- Failure tolerance is exercised: kill one of the 3 reviewers mid-run, confirm the ensemble degrades to N=2 with a note in the combined report.
- Per-ensemble subdirectories exist with `r1.md`, `r2.md`, `r3.md`, `combined.md` for inspection.

## Risks and mitigations

- **Gemini CLI compatibility on Windows.** May need a wrapper. Mitigation: test early in plan, before committing to the architecture.
- **Concurrent spawn complexity in PowerShell.** `Start-Job` + `Wait-Job` works but has quirks. Mitigation: prefer `Start-Process` + file-based synchronization for predictability.
- **Handler synthesis quality degrades on truly disagreeing reports.** Mitigation: handler prompt explicitly handles "all 3 disagree" by flagging instead of force-merging.
- **Cost surprise** if Opus handler runs longer than expected on big diffs. Mitigation: cap input size at ~50k tokens (truncate if exceeded) and measure on real runs before generalizing.

## Out of scope

- Changing the orchestrator. (Proposal 05.)
- Plan-review ensemble. (Possible follow-up.)
- Local LLM backend. (Possible follow-up — see open question 2.)
- Multi-finding decision-tree application by the handler. (Possible follow-up — see open question 4.)
