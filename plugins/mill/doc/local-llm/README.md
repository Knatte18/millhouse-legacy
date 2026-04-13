# Local LLM research notes

Research notes from evaluating local and alternative LLM backends for code
review work. Two passes, both on RTX 5090 / WSL2 / Windows 11.

## Reading order

1. **`lessons-vllm-tooluse.md`** — Pass 1 (April 2026, abandoned). First
   attempt: Qwen3-Coder via vLLM with full Anthropic tool-use protocol.
   Failed for architectural reasons. Verdict: tool-use multi-turn is the
   wrong dispatch mode for review work, regardless of model.

2. **`benchmarks.md`** — Pass 2 (April 2026, accepted). Bulk-mode dispatch:
   pre-assembled prompts, no tool use. Tested across many models —
   qwen3.5, GLM-4.7-Flash, DeepSeek R1, Gemini 3 Flash/Pro/Flash-Lite,
   Sonnet 4.6, Opus 4.6. Recommended model matrix, ensemble strategy,
   rate-limit findings.

3. **`ollama-guide.md`** — Operational reference for running Ollama
   locally. Setup, recommended models, context-size vs speed table,
   thinking-mode pitfalls, network exposure, single-GPU parallelism limit.

## Headline findings

- **vLLM is not worth the setup cost** on WSL2 + Blackwell. FP8 KV cache is
  10x slower (broken dxgkrnl path), nvcc + CUDA toolkit install is fragile,
  startup is 45-60s. Use Ollama instead.
- **Tool-use dispatch fails on smaller code models.** Qwen3-Coder loops,
  hallucinates findings, and corrupts files. Bulk single-shot dispatch is
  the only reliable mode for non-frontier reviewers.
- **Local single-GPU cannot do parallel ensemble.** A 30B model + KV cache
  fills 32 GB VRAM. Concurrent reviewer instances queue serially. Cloud
  providers (Gemini Pro × 3, Sonnet) handle parallelism remotely and stay
  inside one wall-clock window.
- **GLM-4.7-Flash is the best local reviewer tested.** Matches Sonnet
  --effort max on unique findings at 2.5x the speed (71s vs 178s).
- **Gemini 3 Pro is non-deterministic** — separate runs return different
  findings, ensemble of 3 catches significantly more than any single run.
  Has aggressive undocumented per-IP rate limits even on AI Pro.
- **qwen3.5:27b with thinking mode** is a solid local fallback if you don't
  want GLM. Slower (~150s) but very thorough.
- **qwen3-coder:30b without thinking** is too shallow for serious review.
  Use qwen3.5 variants instead.

## Hardware

- GPU: RTX 5090 (32 GB GDDR7)
- CPU: Ryzen 7 9800X3D
- RAM: 64 GB DDR5 6000 MHz
- OS: Windows 11 Pro + WSL2 (Debian Trixie)

Numbers in `benchmarks.md` only generalise within a few percent to other
RTX 50-series cards. 24 GB cards cut you out of 30B+ models at usable
context sizes.
