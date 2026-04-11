# Benchmark Results

All benchmarks from 2026-04-11 on:
- **GPU:** NVIDIA RTX 5090 (32 GB GDDR7, Blackwell architecture)
- **CPU:** AMD Ryzen 7 9800X3D
- **RAM:** 64 GB DDR5 6000 MHz
- **SSD:** 2 TB Gen 5 NVMe
- **OS:** Windows 11 Pro + WSL2 (Debian Trixie)
- **Model:** Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit (cpatonn/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit)
- **vLLM:** 0.19.0
- **Ollama:** 0.20.5
- **CUDA toolkit:** 12.9 (driver 595.97)

## Methodology

- All vLLM tests via Anthropic Messages API (`/v1/messages`), non-streaming
- All Ollama tests via `/api/chat`, `stream: false`
- Warmup request sent before each test series (first request after model load is always slower)
- tok/s calculated as `output_tokens / wall_time_seconds` (vLLM) or `eval_count / (eval_duration / 1e9)` (Ollama, which reports internal timing)
- Each measurement confirmed across 3-5 runs for consistency

## vLLM Configuration Impact

How different vLLM flags affect performance. All tests: 500 token review output.

| Configuration | tok/s | Notes |
|--------------|-------|-------|
| fp8 kv-cache, 200K, expert-parallel | **20** | fp8 emulated in software on WSL2 — 10x penalty |
| no fp8, 32K, no expert-parallel | 142 | Baseline without MoE optimization |
| no fp8, 32K, enforce-eager | **57** | CUDA graphs disabled — 2-3x penalty |
| **no fp8, 32K, expert-parallel** | **177** | Best single-user speed |
| **no fp8, 64K, expert-parallel** | **139** | Recommended production config |
| no fp8, 100K, expert-parallel | **26** | Speed collapses — VRAM pressure on KV cache |

### Key takeaways

1. **Never use fp8 kv-cache on WSL2** — 10x slower (dxgkrnl limitation)
2. **Always use `--enable-expert-parallel`** for MoE models — 15-20% improvement
3. **Never use `--enforce-eager`** — CUDA graphs are faster for batch size 1
4. **64K is the sweet spot** — 139 tok/s with enough context for any review
5. **100K context collapses speed** — same speed as Ollama at that point

## vLLM vs Ollama: Single-User

### At matched context sizes

| Context | vLLM tok/s | Ollama tok/s | vLLM advantage |
|---------|-----------|-------------|----------------|
| 8K | ~139* | ~52 | 2.7x |
| 16K | ~139* | ~26 | 5.3x |
| 32K | 177 | 26 | 6.8x |
| 64K | 139 | 26 | 5.3x |
| 100K | 26 | 24 | 1.1x (no advantage) |

*vLLM at 64K config handles 8K and 16K prompts at 139 tok/s — context allocation is fixed at startup, not per-request.

### Why Ollama appears faster in naive benchmarks

Ollama's default `num_ctx` is 2048 tokens. At 2K context it delivers 177 tok/s — competitive with vLLM. But 2K context is useless for real work (code review needs 8K+ minimum).

Many online benchmarks use Ollama's defaults, producing misleadingly high numbers. Always check what `num_ctx` was used.

## vLLM vs Claude Sonnet API

| Metric | vLLM 64K | Sonnet 4.6 API |
|--------|---------|----------------|
| Output speed | 139 tok/s | 66 tok/s |
| Context limit | 64K | 200K |
| Cost | Free | $3/M input, $15/M output |
| Rate limiting | None | Yes |
| Network latency | 0ms | Variable |
| Availability | Requires GPU + setup | Always available |
| Model quality | Good (Qwen3-Coder) | Excellent (Claude) |

**vLLM is 2.1x faster and free.** For automated review gates where Claude-level quality isn't critical, local Qwen is the better choice.

## Concurrent Request Scaling

### vLLM (32K context, expert-parallel)

| Concurrent | Total tokens | Wall time | Aggregate tok/s | Worst latency |
|-----------|-------------|-----------|-----------------|---------------|
| 1 | 500 | 2.8s | 177 | 2.8s |
| 3 | 1,368 | 4.7s | 292 | 4.7s |
| 5 | 2,390 | 4.8s | 497 | 4.8s |

vLLM uses continuous batching — all requests processed simultaneously on the GPU. Throughput scales nearly linearly. Latency per request increases only ~65% from 1 to 5 concurrent.

### Ollama (2K context — inflated speed)

| Concurrent | Total tokens | Wall time | Aggregate tok/s | Worst latency |
|-----------|-------------|-----------|-----------------|---------------|
| 1 | 399 | 2.4s | 208 | 2.4s |
| 3 | 1,217 | 6.6s | 184 | 6.6s |
| 5 | 1,980 | 10.2s | 194 | 10.2s |

Ollama processes requests **sequentially**. The staircase pattern is visible: request 1 finishes at 2.4s, request 2 at 4.4s, request 3 at 6.6s. At realistic 32K context (26 tok/s single), 5 concurrent requests would take ~60s.

### Concurrent winner

At any concurrency > 1, vLLM wins decisively. At 5 concurrent with realistic context, vLLM is estimated **10x+ faster** than Ollama in total completion time.

## Context Length Limits (VRAM)

### vLLM (AWQ 4-bit, fp16 KV cache)

| max-model-len | KV cache needed | Available | Status |
|---------------|-----------------|-----------|--------|
| 32,768 | ~5.5 GiB | ~12 GiB | OK |
| 65,536 | ~8.3 GiB | ~12 GiB | OK |
| 100,000 | ~10 GiB | ~12 GiB | OK (speed collapses) |
| 131,072 | 12.0 GiB | 11.88 GiB | FAIL (0.12 GiB short) |
| 200,000 | ~18 GiB | ~12 GiB | FAIL |

With fp8 KV cache: all sizes fit, but inference is 10x slower on WSL2.

### Ollama (GGUF Q4_K_M)

Ollama supports 200K+ context. GGUF quantization format uses less VRAM for KV cache than AWQ + fp16. But speed drops regardless of available VRAM.

## Tool Use Performance

Via `claude --bare -p` with vLLM, 64K context:

| Tool | Turns | Wall time | Result |
|------|-------|-----------|--------|
| Read (.env.example) | 2 | 17.7s | Correct |
| Grep (count matches) | 4 | 15.9s | Correct |
| Write (create file) | 4 | 4.0s | Correct |

Tool use adds latency due to multi-turn round-trips. Each turn involves: model generates tool call → Claude Code executes → result sent back → model processes.

## Prefix Caching

vLLM with `--enable-prefix-caching`, sequential requests with identical system prompt:

| Request | Wall time |
|---------|-----------|
| First (cold) | 2,503ms |
| Second (warm) | 2,265ms |
| Third (warm) | 2,309ms |

~10% improvement. Effect is larger with longer shared prefixes. Millhouse review templates are ~1-2K tokens — prefix caching saves prompt processing time on repeated reviews.

## Startup Time

### vLLM

| Phase | Cold | Warm (cached) |
|-------|------|---------------|
| Model loading | ~20s | ~10s |
| torch.compile | ~15s | ~3s |
| CUDA graph profiling | ~10s | ~10s |
| **Total** | **~45-60s** | **~20-30s** |

### Ollama

| Phase | Duration |
|-------|----------|
| Model loading | ~6-8s |
| **Total** | **~6-8s** |

Ollama starts 3-8x faster. But you start once and leave running — startup time is irrelevant for steady-state use.

## External Benchmark Sources

- [RTX 5090 vs 4090 Ollama + LM Studio benchmarks](https://vipinpg.com/blog/benchmarking-rtx-5090-vs-4090-for-local-llm-inference-real-world-tokensecond-gains-with-ollama-and-lm-studio/) — confirms Ollama 26 tok/s at 32K for ~30B models
- [Optimizing Qwen3 Coder for RTX 5090](https://www.cloudrift.ai/blog/optimizing-qwen3-coder-rtx5090-pro6000) — vLLM concurrent throughput benchmarks
- [Claude Sonnet 4.6 benchmarks](https://artificialanalysis.ai/models/claude-sonnet-4-6-adaptive) — 66 tok/s via Anthropic API
- [FP8 slower on RTX 5090 WSL2](https://github.com/vllm-project/vllm/issues/37242) — confirms dxgkrnl FP8 limitation
