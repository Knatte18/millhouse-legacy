# Ollama Guide

How to install, configure, and run Ollama for local LLM inference. Ollama uses llama.cpp (pure C++) and runs natively on Windows.

## Why Ollama

- **Simple setup** — one installer, one command to pull a model
- **Native Windows** — no WSL required
- **Supports 200K+ context** — GGUF format has compact KV cache
- **Good for quick testing** — fast startup, no compilation step

## Why NOT Ollama (as primary)

- **No Anthropic Messages API** — needs LiteLLM proxy for `claude --bare -p`
- **Sequential request processing** — no continuous batching, concurrent requests serialize
- **Slow at realistic context sizes** — 26 tok/s at 32K+ context (vs vLLM's 139 tok/s)
- **Context size destroys speed** — 177 tok/s at 2K drops to 26 tok/s at 32K

## Installation

Download from [ollama.com](https://ollama.com) and run the installer. Ollama runs as a Windows service.

### Pull a Model

```powershell
ollama pull qwen3-coder:30b
```

This downloads ~18 GB (GGUF Q4_K_M quantization).

### Verify

```powershell
ollama list
```

Should show `qwen3-coder:30b` with size and modification date.

## Running Ollama

Ollama runs as a background service on Windows. It starts automatically and listens on port 11434.

### Quick test

```powershell
ollama run qwen3-coder:30b "Hello, what model are you?"
```

### API test

```powershell
curl http://localhost:11434/api/chat -d '{"model":"qwen3-coder:30b","messages":[{"role":"user","content":"Hello"}],"stream":false}'
```

## Context Size Configuration

**This is critical.** Ollama's default context is 2048 tokens — far too small for any real work. The default gives misleadingly high tok/s numbers.

### Per-request

Set `num_ctx` in the options:
```json
{
  "model": "qwen3-coder:30b",
  "messages": [{"role": "user", "content": "..."}],
  "options": {"num_ctx": 32768}
}
```

**Warning:** Changing `num_ctx` forces a model reload (~6s). Keep it consistent across requests.

### Permanent (via Modelfile)

Create a custom model with a fixed context size:

```powershell
ollama create qwen3-coder-32k -f - <<EOF
FROM qwen3-coder:30b
PARAMETER num_ctx 32768
EOF
```

Then use `qwen3-coder-32k` instead of `qwen3-coder:30b` to avoid reload on every request.

### Context Size vs Speed

Benchmarked on RTX 5090 (32GB), Qwen3-Coder-30B, 89 token output:

| num_ctx | tok/s | Notes |
|---------|-------|-------|
| 2,048 (default) | 177 | Unusable context size — misleading speed |
| 8,192 | ~52 | Minimum for simple tasks |
| 16,384 | ~26 | Minimum for code review |
| 32,768 | 26 | Recommended for reviews |
| 65,536 | 26 | |
| 100,000 | 24 | |
| 200,000 | 35* | *Anomalous — may be measurement variance |

External benchmarks confirm these numbers:
- Qwen 2.5 32B Q6_K at 8K: 51.8 tok/s, at 32K: 26.3 tok/s ([source](https://vipinpg.com/blog/benchmarking-rtx-5090-vs-4090-for-local-llm-inference-real-world-tokensecond-gains-with-ollama-and-lm-studio/))

**Bottom line:** At any usable context size (8K+), Ollama delivers 26-52 tok/s. The 200 tok/s number only applies at 2K context.

## Concurrent Requests

Ollama processes requests **sequentially**. There is no continuous batching. With 5 concurrent requests, each waits for the previous to finish:

| Concurrent | Wall time | Aggregate tok/s | Last-request latency |
|-----------|-----------|-----------------|----------------------|
| 1 | 2.4s | 208* | 2.4s |
| 3 | 6.6s | 184* | 6.6s |
| 5 | 10.2s | 194* | 10.2s |

*Measured at 2K context (default). At 32K context, single request is 26 tok/s, making concurrent even worse.

Compare with vLLM (32K context): 5 concurrent requests finish in 4.8s with 497 tok/s aggregate.

## Using Ollama with Claude Code

Ollama does not speak Anthropic Messages API. To use `claude --bare -p`, you need LiteLLM as a proxy.

### Install LiteLLM

```powershell
pip install litellm
```

Or in WSL:
```bash
pip install litellm
```

### Configure LiteLLM

Create `litellm-config.yaml`:
```yaml
model_list:
  - model_name: "default"
    litellm_params:
      model: ollama/qwen3-coder:30b
      api_base: http://localhost:11434

litellm_settings:
  drop_params: true
  request_timeout: 600

general_settings:
  disable_key_check: true
```

### Start LiteLLM

```powershell
litellm --config litellm-config.yaml --port 4000
```

### Use from Claude Code

```powershell
$env:ANTHROPIC_BASE_URL = "http://localhost:4000"
$env:ANTHROPIC_API_KEY = "dummy"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = "default"
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = "default"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = "default"
claude --bare -p "Say hi" --model default
```

### LiteLLM Security Warning

LiteLLM PyPI versions 1.82.7 and 1.82.8 were compromised with credential-stealing malware. Do not install these versions. Check your version after install:
```powershell
pip show litellm
```

## Tool Use with Ollama

Ollama supports function calling via its OpenAI-compatible API. Qwen3-Coder has native tool calling support. When using via LiteLLM + `claude --bare -p`, tool use (Read, Write, Grep) should work, but this has **not been tested** as thoroughly as vLLM's direct integration.

## GPU Sharing

Ollama (Windows) and vLLM (WSL) cannot run simultaneously — both need the full GPU. Startup scripts should kill one before starting the other:

```powershell
# Kill Ollama before starting vLLM
Stop-Process -Name "ollama" -Force -ErrorAction SilentlyContinue
```

```powershell
# Kill vLLM before using Ollama
wsl -e bash -c "pkill -f 'vllm serve'"
```

## Ollama API Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chat` | POST | Chat completion |
| `/api/generate` | POST | Text completion |
| `/api/tags` | GET | List installed models |
| `/api/show` | POST | Model details |
| `/api/pull` | POST | Download model |

Response includes timing fields useful for benchmarking:
- `eval_count`: number of output tokens
- `eval_duration`: generation time in nanoseconds
- `prompt_eval_count`: number of input tokens
- `prompt_eval_duration`: prompt processing time in nanoseconds
- `load_duration`: model loading time (if reloaded)

Calculate tok/s: `eval_count / (eval_duration / 1e9)`
