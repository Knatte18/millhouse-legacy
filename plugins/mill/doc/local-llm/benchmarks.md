# Pass 2: Bulk-mode benchmark across many models (April 2026)

> **Prequel:** Pass 1 (`lessons-vllm-tooluse.md`) abandoned tool-use dispatch
> as architecturally wrong for review work. Pass 2 starts from that
> conclusion: bulk-mode dispatch only, full file content pre-bundled in the
> prompt, no tool calls. The question is whether *any* current model — local
> or cloud — beats the previous default of Sonnet alone.

Empirical comparison of review-quality across many models on real-world tasks.

**Hardware:** RTX 5090 (32 GB VRAM), Ryzen 7 9800X3D, 64 GB RAM
**Date:** 2026-04-12

## Important correction: Gemini Flash retested as ensemble (2026-04-13)

The Pass 2 numbers below evaluate each model as a **single reviewer call**
and rank them on per-call depth. This methodology made Gemini 3 Flash look
shallow ("first-pass only", "less precise references", 3-4 critical
findings per call). That conclusion is **wrong as a recommendation**
because it asks the wrong question.

A follow-up test ran **4 × Flash workers in parallel** on a real review
artifact and produced:

- **17 unique critical findings** (vs 3-4 per single call)
- **0 hallucinations** across all 17 findings
- **53% singletons** — only one of four workers found each finding (high variance per worker)
- **Only 24% convergence** (≥2 workers agree) — Flash workers explore very different reasoning paths
- **~30s per worker, all parallel → ~30s wall clock**

The right unit of comparison is **strategy**, not model. "Single deep call"
(Sonnet --effort max, ~250s, 6 findings) and "shallow ensemble" (4 × Flash,
~30s, ~17 findings) are different strategies. Per-call depth is irrelevant
when you can run several calls in parallel for free.

**Updated recommendation: 4-6 × Gemini Flash workers + 1 handler call (Pro
or Sonnet) for verification + dedup.** This is faster, cheaper, and finds
more bugs than any single-call strategy. The single-call rankings below
are kept for transparency but are not the right starting point for a
review pipeline.

The "Flash gives general observations / less precise references" framing
in the tables below applies to **one** Flash call. With 4 in ensemble,
each one is still shallow individually, but the union covers more ground
than a single deep reviewer.

## TL;DR (revised)

For **cloud review without burning Claude tokens** (the common case on a
laptop without a GPU): **4-6 × Gemini Flash workers in parallel + 1 handler
call** (Pro or Flash) for verification and dedup. Wall clock ~60-90s,
catches ~15-17 unique findings, 0 hallucinations observed, all within a
single Gemini AI Pro/Ultra subscription.

For **local review on a single GPU**: **GLM-4.7-Flash** is the best
single-call local reviewer tested (71s, matches Sonnet --effort max on
unique findings). Single-GPU systems can't parallelise local workers —
the model + KV cache fills VRAM — so ensemble strategies belong in the
cloud.

For **single-reviewer subtle-bug hunting** (when speed doesn't matter and
you want one deep reviewer): Sonnet --effort max remains the gold standard.
~250s per call, hard to parallelise cheaply, burns Claude tokens.

## Summary

**Verdict by use case:**

| Use case | Best model | Why |
|---|---|---|
| Code review with exact line numbers + subtle bugs | **Sonnet --effort max** | Most precise, catches intentional code too (needs filter) |
| **Fast + high quality local review** | **GLM-4.7-Flash (Ollama, thinking)** | **2.5x faster than Sonnet, matches its unique findings** |
| Fast first-pass cloud review | Gemini 3 Flash (CLI) | 10x faster than Sonnet, good structure |
| Free local review (alternative) | qwen3.5:27b (Ollama, thinking) | Solid quality, slower (150s) |
| Fast local pre-screen | qwen3:30b-thinking (Ollama) | 32.9s, but less precise |
| **Ensemble review** | **All 3 cloud + GLM in parallel** | **~200s wall clock, union of all findings** |

## Test 1: mill-go SKILL.md review

**Task:** Review a 600-line workflow spec for design issues, gaps, contradictions.

| Model | Time | Lines output | Critical findings | Notes |
|---|---|---|---|---|
| qwen3-coder:30b (no thinking) | 15s | 112 | 3 | Overfladisk |
| qwen3.5:35b-a3b (thinking, MoE) | 35s | 176 | 5 | Sonnet-level |
| **qwen3.5:27b (thinking, dense)** | **80s** | **241** | **14+** | **Most detailed** |
| deepseek-r1:32b (thinking) | 86s | 74 | 3 | Disappointing |
| Gemini 3 Flash (CLI, free tier) | 102s | 48 | 4 | Systemic focus |
| Sonnet 4.6 | 178s | 122 | 5 | Deep, actionable |
| **Opus 4.6** | **176s** | **93** | **5** | **Most precise findings** |

### Key insights from Test 1

- **qwen3.5:27b** found bugs no other model caught:
  - Code review agent can't read own report (instruction self-contradiction)
  - TDD false positive on pre-implemented functionality
  - notify.sh existence check missing
  - Push failure handling missing
- **Opus** had fewest findings but each was surgical — exact line, exact fix, cited root cause
- **qwen3-coder:30b** without thinking is too shallow for serious review
- **deepseek-r1:32b** was disappointing — despite best reasoning benchmarks

## Test 2: Real Python code review (py/priceindex)

**Task:** Review 3 files (~700 lines) from a price index calculation library.

| Model | Time | Bugs found | Quality |
|---|---|---|---|
| qwen3.5:27b (thinking) | 159s | 5 real bugs | Concrete, actionable |

**Bugs qwen3.5:27b found:**

1. Date arithmetic crash (`t0.month + 3` overflow for Q4 dates)
2. IndexError on sparse rolling windows (`.iloc[-2]` without len-check)
3. Index mapping error (relative indices passed to original df after sort)
4. None handling in `min()` (TypeError)
5. Count data alignment (silent pandas reindex drop → 0s filled)

All 5 are **real production bugs** with concrete fixes.

## Test 3: Pipeline review (py/priceindexprocessing)

**Task:** Review 8 files (~1200 lines) implementing a data pipeline — partitions, LORSI, CBI, I/O.

| Model | Time | Gen tok/s | Critical | Notes |
|---|---|---|---|---|
| **Gemini 3 Flash** (cloud) | **21s** | — | 3 | General, less precise references |
| **qwen3:30b-thinking** (Ollama) | **32.9s** | **134** | 4 | Fast but hallucinates some |
| **GLM-4.7-Flash** (Ollama) | **71.8s** | **110** | **4 unique** | **Best local quality — matches Sonnet** |
| **qwen3.5:27b** (Ollama, thinking) | 150s | 58 | 5 | Solid but slow |
| **Sonnet 4.6 normal** | 201s | — | 4 | Deepest, exact line numbers |
| **Sonnet 4.6 --effort max** | **178s** | — | **5** | **Maximum precision** |

### Findings overlap

Most models found:
- Logging config race (basicConfig called multiple times)
- RSI_stop_date IndexError on sparse data
- LORSI parallelization opportunity
- Infinite loop risk in `cluster_adj_neighbors`

### Unique findings per model

**Sonnet 4.6 --effort max (unique):**
- **Module-level execution**: `pipeline.py:369` calls `update_all_data()` at top-level → double execution
- **`LORSIPartitionClass.copy()` drops `std_ratio` silently** — precise positional arg analysis
- **`intersects` vs `touches`** in `compute_geodata_dist_matrix` — floating-point precision issue
- **Deprecated `fillna(method=...)`** API removed in pandas 2.2
- **GCS upload commented out** (`pipeline.py:135`) — output never published in production

**GLM-4.7-Flash (unique, matches Sonnet --effort max on several):**
- **GCS upload commented out** — only this and Sonnet --effort max caught it
- **`np.log(0)` crash risk** in `filter_RS_for_outliers` — **no other model caught this**
- Atomic write pattern missing (non-atomic blosc writes)
- Floyd-Warshall O(V³) performance bottleneck analysis

**qwen3.5:27b (unique):**
- Non-atomic PAF file writes (missing tmp+rename pattern)
- Stale metadata freshness check missing

**qwen3:30b-thinking (unique):**
- CBI weight calculation fundamental flaw (false positive — misread the design)
- Partition numbering uniqueness concern

**Gemini 3 Flash (unique):**
- Spatial join CRS precision issues
- Circular outlier logic dependency

### Quality analysis

- **Sonnet --effort max** and **GLM-4.7-Flash** both found the `GCS upload commented out` bug — *no other model did*
- **GLM-4.7-Flash found `np.log(0)` crash** that even Sonnet missed
- **Sonnet gives exact line numbers** (`pipeline.py:369`)
- **GLM-4.7-Flash gives function-name precision** with concrete fixes
- **qwen3.5:27b gives "~line X" estimates**, less precise but actionable
- **qwen3:30b-thinking hallucinated some findings** — not always domain-correct

### Winner: GLM-4.7-Flash (local) or Sonnet --effort max (cloud)

For local Ollama use, **GLM-4.7-Flash is the clear winner**:
- Matches or exceeds qwen3.5:27b in every dimension
- Faster (72s vs 150s)
- Found bugs that only Sonnet --effort max also caught
- Has unique findings (np.log(0))
- 198K context window

## Performance Characteristics

### Generation speed (qwen3.5:27b on RTX 5090)

| num_ctx | tok/s |
|---|---|
| 2,048 (default) | 177 (unusable — context too small) |
| 8,192 | ~52 |
| 16,384 | ~26 |
| 32,768 | 60 |
| 65,536 | 45 |
| 131,072 | 29 |
| 262,144 | 7 |

**Recommended:** 32-64K context for most work. Above 64K, speed drops significantly due to VRAM/KV-cache pressure.

### Model size vs RAM usage

| Model | Size | Context @ 32K works? | Context @ 256K works? |
|---|---|---|---|
| qwen3-coder:30b | 18.6 GB | Yes | Yes |
| qwen3.5:27b | 17.4 GB | Yes | Yes |
| qwen3.5:35b-a3b | 23.9 GB | Yes | Yes |
| deepseek-r1:32b | 19.9 GB | Yes | Yes |

All Ollama models fit full 262K context on RTX 5090 32GB. Ollama is much more VRAM-efficient than vLLM for KV cache.

### Warm vs cold model (qwen3.5:27b)

| State | Wall time (500 tok output) |
|---|---|
| Cold (first call, includes load) | ~12.6s |
| Warm (keep_alive: -1) | ~8.4s |
| Warm, 10 consecutive calls | ~8.4s each (no degradation) |

**Setting `keep_alive: -1`** eliminates the ~4s load cost per call. Use for all Millhouse calls.

## Thinking Mode Gotcha

Qwen3.5 models (and DeepSeek R1) use internal thinking tokens that count against `num_predict`. **Must budget for both thinking AND content.**

| `num_predict` | Thinking | Content | Result |
|---|---|---|---|
| 500 | ~500 | 0 | **FAIL** — thinking ate all budget |
| 4,000 | ~4,000 | 0 | **FAIL** — still not enough |
| 8,000 | ~7,000 | 0 | **FAIL** |
| **20,000** | ~5,000 | ~15,000 | **Works** |
| 24,000 | ~7,000 | ~17,000 | Works |

**Rule:** Always set `num_predict >= 20000` when thinking is enabled on qwen3.5 models. Thinking traces can be long (15-20K chars).

## Ensemble Review Strategy

Running **all 3 models in parallel** is cost-effective:

- **Gemini Flash**: 21-30s, ~free (1000 req/day on free tier)
- **qwen3.5:27b**: 150-160s, free (local)
- **Sonnet 4.6**: 200s, paid (~$0.10 per review)

**Wall clock time:** max(Gemini, Qwen, Sonnet) ≈ 200s (same as Sonnet alone)
**Additional cost over Sonnet-alone:** ~$0 (Gemini free, Qwen free)
**Added findings:** Union of all three catches bugs any single model missed

### Parallel execution

Since Gemini and Sonnet are cloud APIs and Qwen is local GPU, all three can run simultaneously without contention. Ollama holds GPU, the cloud calls hit network concurrently.

## Known Limitations

1. **qwen3-coder:30b has no thinking mode** — it's code-only trained. Use qwen3.5 variants for thinking.
2. **Gemini CLI free tier has per-minute rate limits** — can cause multi-second retry waits mid-review
3. **Gemini 3 Pro has aggressive rate limiting even on AI Pro** — benchmarking with several tens of calls within an hour triggered a temporary IP block. AI Pro's advertised "1500 req/day" isn't the real limit — there's an undocumented per-hour/per-IP cap that kicks in much sooner under sustained load. Bursty usage is fine, but running parallel ensemble reviews continuously can get your IP throttled or blocked. Plan around this: space out requests, use backoff, or fall back to Sonnet when Gemini stalls.
4. **All local reviews are wall-time bound by generation speed** — no amount of context-size or thinking helps if you need the response in <30s
5. **Tool use with qwen3-coder:30b was unreliable in prior vLLM tests** — loops, hallucinations, tool call format breaks. qwen3.5:27b via Ollama direct API has been reliable so far (tested on trivial tool-use tasks).
6. **Gemini Pro is non-deterministic** — separate runs on the same prompt return different findings. Empirically, 3 parallel runs found ~10 unique critical bugs combined vs ~3-4 per single run. This is both a feature (ensemble gives coverage) and a risk (a single run may miss bugs the next run catches).
7. **Single-GPU setups cannot do ensemble locally** — GLM-4.7-Flash/qwen3.5:27b take 17-19 GB VRAM + KV cache, leaving no room for concurrent instances. Local ensemble becomes sequential (~3x slower wall clock), losing the main benefit of non-deterministic reviewers.

## Recommendations for Millhouse

**For plan review (catches design issues before implementation):**
- Primary: Sonnet (exact line references, subtle bugs)
- Secondary: qwen3.5:27b or Gemini Flash for fast iteration

**For code review (catches bugs in diffs):**
- Primary: Sonnet (same reasons)
- Acceptable: qwen3.5:27b for rapid iteration rounds

**For discussion review (gaps in problem statement):**
- Opus or Sonnet — requires creative gap identification

**For "tripwire" pre-screening:**
- qwen3.5:27b or Gemini Flash — fast, cheap, catches obvious issues

**For important reviews where you want maximum coverage:**
- **Ensemble: 4-6 × Gemini Flash workers in parallel + 1 handler call** (Pro
  or Flash for verifier role). Wall clock ~60-90s, ~15-17 unique critical
  findings, all within Gemini subscription (no Claude tokens). This was the
  best strategy in follow-up testing.
- **Alternative: 3 × Gemini Pro + Flash verifier** (~125s) — fewer workers,
  more depth per worker, similar coverage.
- **Watch for rate limits** — sustained ensemble use can trigger Gemini IP
  throttling. Plan a fallback to Sonnet.

## Model Recommendation Matrix

| Scenario | Model |
|---|---|
| Subtle bug hunting on production code | Sonnet / Opus |
| Spec/workflow review (lots of findings needed) | qwen3.5:27b |
| Fast iteration on non-critical code | Gemini 3 Flash |
| Free, local, decent quality | qwen3.5:27b (thinking, 32K ctx, 20K predict) |
| Speed > quality | Gemini 3 Flash |
| Maximum coverage | Ensemble (all 3 parallel) |
| Offline/air-gapped | qwen3.5:27b (only local option) |
