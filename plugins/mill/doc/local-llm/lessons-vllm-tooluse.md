# Pass 1: vLLM + tool-use dispatch (abandoned April 2026)

**Status:** Abandoned. Local LLM as a **tool-use** review backend is not
viable with current-generation small/medium code models. This document
captures why.

> **Sequel:** Pass 2 (see `benchmarks.md`) revisits the same goal with a
> different dispatch mode (bulk single-shot, no tool use) and several newer
> models. Pass 2 succeeds where Pass 1 failed for sequential review, but
> still cannot match cloud providers on parallel ensemble due to single-GPU
> contention. Read both passes together for the full picture.

---

## Context

In April 2026 we attempted to use a local LLM backend for plan and code
review, with the goal of saving frontier-model API tokens and speeding up
review loops. The first implementation used:

- **Model:** Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit
- **Inference engine:** vLLM on WSL2 / RTX 5090
- **Dispatch:** `claude -p` with `ANTHROPIC_BASE_URL` pointed at vLLM (vLLM
  exposes an Anthropic Messages API)
- **Protocol:** full Anthropic tool-use (Read/Write/Edit/Grep/Bash),
  multi-turn

We benchmarked Qwen head-to-head against Sonnet on a real refactoring task
for both plan review and code review. The results were conclusive enough
to abandon this approach entirely.

---

## Results

### Plan Review — Round 1

| Metric | Qwen | Sonnet |
|--------|------|--------|
| Duration | 4:00 | 2:46 |
| Exit | crashed (exit 1 during fix phase) | success |
| Findings | 5 BLOCKING + 2 NIT | 3 BLOCKING + 4 NIT |
| Accurate findings | 0 of 7 | 7 of 7 |
| plan.md state after | corrupted (reverted from backup) | cleanly modified |

Qwen's findings were all variants of "this section is missing details" pointed at sections of the plan that were fully specified. It pattern-matched the expected output format (findings with severity labels) and generated plausible-sounding objections without actually reading the Requirements sections it was critiquing. Then it tried to "fix" these non-issues in plan.md and crashed, corrupting the file.

Sonnet found 7 real issues and fixed 4 of them cleanly. Round 2 and Round 3 (Sonnet only, we abandoned Qwen after Round 1) each found additional real issues introduced or exposed by the previous fix — exactly what an iterative review loop is supposed to do.

### Code Review — Round 1

| Metric | Qwen | Sonnet |
|--------|------|--------|
| Duration | ≥5:00 then killed | 3:26 |
| Exit | infinite generation loop, manually aborted | success |
| Verdict | never emitted | APPROVE + 3 NIT |

On a larger input surface (8 files, ~340-line diff, ~1000+ lines of source to evaluate), Qwen entered a sustained generation state at ~23 tok/s with `Avg prompt throughput: 0.0` — meaning the model was generating text without emitting any tool call for the client to act on. GPU KV cache grew slowly (26% → 31% over 5 minutes) indicating raw token generation, not useful work. Prefix cache hit rate stuck at 94.5% (no new input entering the pipeline).

The tool-use state machine degenerated. The model could not decide which tool to call next and fell into a repetition / runaway-reasoning mode.

Sonnet reviewed the same diff in 3:26 with an APPROVE verdict and 3 informational NITs (all cosmetic documentation issues).

---

## Why it failed

The problems are architectural, not engine-level. Switching from vLLM to Ollama or to a different model class would not fix them.

### 1. Tool-use multi-turn overhead dominates wall time

Each tool-use turn has fixed overhead: client parses the response, executes the tool, sends the result back, the inference engine re-processes the full conversation history (prefix caching helps but doesn't eliminate it). For a small review task, the observed pattern was ~20 turns × ~10s = ~200 seconds, most of which was not model inference at all — it was transport, parsing, and file I/O.

Qwen's per-token generation speed (80–110 tok/s observed, 139 tok/s benchmarked at 64K context) is actually higher than Sonnet's API speed (~66 tok/s). Per-token, the local model is faster. But per-turn, the overhead is the same, and Qwen's verbose output (emojis, nested headings, restated context) produces more tokens per turn. Net result: Sonnet is 30% faster end-to-end despite being "slower" per token.

### 2. Tool-use protocol fragmentation

Anthropic `tool_use` blocks ≠ OpenAI function calling ≠ Qwen3 XML ≠ Gemini function declarations. Building a cross-backend tool-use dispatcher that works reliably across all providers is expensive and fragile. We observed Qwen generating tool calls with stripped forward slashes in absolute Windows paths, creating stray directories at the project root. Every backend has its own tool-use quirks.

### 3. Adaptive exploration is wasted on structured review work

For plan review, the file set is deterministic: the plan's `## Files` section lists it explicitly. For code review, the file set is `git diff <plan_start>..HEAD`. The reviewer does not need to discover which files to read — it just needs to evaluate files it already knows. The whole point of tool-use (adaptive exploration) is overhead that provides no value for this class of work.

### 4. Smaller models cannot sustain tool-use protocols reliably

Qwen's specific failure modes — hallucinated findings, infinite generation loops on large inputs, forward slash stripping, GAP/APPROVE inconsistency, verbose output — are all failures of the multi-turn decision-making required by tool use. A model that can answer a single question well may still lack the metacognition to say "OK, I've read enough files, now I'll write the review file and terminate." The tool-use state machine requires stable long-horizon planning that smaller models don't reliably have.

---

## What would work instead: bulk-mode dispatch

Single-shot, no tool use, orchestrator pre-bundles files.

```
Orchestrator (Claude, runs before dispatch):
  1. Parse plan.md / git diff to determine the file set (deterministic)
  2. Read each file locally using Claude Code's tool use
  3. Build one big prompt:
       <system instructions>
       <task title>
       <constraints>
       <file 1: path + full content>
       <file 2: path + full content>
       ...
       "Evaluate and respond with ONLY: verdict + review text"
  4. POST /v1/messages (no tool use, one round-trip)
  5. Receive plain text response
  6. Parse verdict, write review file locally
```

Expected speedup vs multi-turn tool-use dispatch: ~5x for the same work on the same model.

Other benefits:
- **Cross-backend compatibility.** "Text in, text out" is the lowest common denominator. Any LLM works: vLLM, Ollama (no proxy needed!), Gemini CLI, OpenAI API, Claude API. The dispatcher code is the same regardless of backend.
- **No tool-use protocol fragmentation.** Nothing to serialize, nothing to parse, no path-mangling bugs.
- **No state machine for the model to break.** The model has one job: read the bundled prompt, write the review. No decisions to make about what tool to call next.
- **Better caching.** The prompt prefix is stable (same review template, same system instructions). Prefix caching is maximally effective.

### Prerequisite: atomic plan format

Bulk-mode review requires that the reviewer can evaluate each plan step in isolation — each step must be self-contained with explicit `Creates:` / `Modifies:` fields, so the orchestrator knows exactly which files to bundle. This is Motlin's "atomic plan" approach. Without it, reviewers need to understand step interdependencies, which requires adaptive code exploration, which requires tool use, which lands us back in the same trap.

Atomic plan format is therefore not a stylistic preference — it is an architectural prerequisite for making weaker LLMs viable as reviewers.

---

## Tiered model strategy (target architecture)

| Phase | Model | Mode |
|-------|-------|------|
| Orchestration | Frontier (Opus/Sonnet) | Full tool use |
| Discussion review | Frontier (swappable) | Full tool use, independent threads |
| Plan writing | Frontier | Full tool use (writes atomic plan) |
| **Plan review** | **Any LLM** | **Bulk single-shot** |
| Implementation | Frontier now, cheaper later | Tool use |
| **Code review** | **Any LLM** | **Bulk single-shot** |

Only plan review and code review are candidates for a local or alternative
backend. Discussion review stays on a frontier model because it is open-ended
and may need files the author did not pre-list. Orchestration stays on a
frontier model because it is the thinking layer.

---

## Specific Qwen observations (for the record)

In case anyone retries with Qwen or a similar small code model:

- **Hallucinated findings:** Qwen pattern-matched "review expected to find issues" and generated false positives that looked structurally valid but were factually wrong. 7 of 7 findings on plan review were inaccurate.
- **Infinite generation loops:** On larger inputs (8 files / ~340-line diff), Qwen would enter runaway generation at ~23 tok/s for 5+ minutes without emitting a tool call. Had to kill manually.
- **Path stripping in tool calls:** Absolute Windows paths (`C:/Code/millhouse/...`) had their `/` characters dropped during tool_use block generation, creating stray directories at the project root.
- **Verdict inconsistency:** Qwen labeled findings "GAP" in its output body then concluded with "APPROVE" in the verdict line, contradicting its own review. Parsers should trust the explicit verdict, not the inline labels.
- **Verbose output:** Qwen generated 2–3× more tokens per review than Sonnet, with emojis, nested headings, and restated context. This inflated wall time even though per-token generation was fast.
- **Scope creep during review:** Qwen attempted to create new directories
  during a read-only discussion review.
- **Instruction following:** Qwen ignored "Return only: verdict + file path,
  no preamble" and dumped the full review inline.

---

## Cost / benefit of continuing

Not worth pursuing further with current small/medium code models via
tool-use dispatch:

- **Cost incurred to prove it doesn't work:** WSL2 + CUDA toolkit
  installation (~2 hours), vLLM install + model download (~20 GB),
  start/stop scripts, dispatch protocol — all for ~30 minutes of benchmark
  data showing the approach doesn't work.
- **Cost avoided by stopping now:** protocol-per-backend adapters, debugging
  tool-use quirks for each new provider.
- **What we keep:** the tiered-model architecture and bulk-mode design
  described above. Pass 2 (`benchmarks.md`) builds on this.

