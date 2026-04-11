# vLLM Guide

How to install, configure, and run vLLM for local LLM inference. vLLM is a high-throughput inference server optimized for GPU serving with continuous batching.

## Why vLLM

- **Native Anthropic Messages API** (`/v1/messages`) — `claude --bare -p` works directly, no proxy needed
- **139 tok/s at 64K context** on RTX 5090 — 2x faster than Claude Sonnet API (66 tok/s)
- **Continuous batching** — concurrent requests scale linearly (497 tok/s at 5 concurrent)
- **Prefix caching** — repeated prompt prefixes (review templates) cached across requests
- **Tool use** — Read, Write, Grep work through native tool calling

## Installation

### In WSL2

```bash
pip install vllm
```

If the system Python is externally managed (Debian Trixie), either use `--break-system-packages` or install in a venv. See [WSL2 GPU Setup](wsl2-gpu-setup.md) for Python environment details.

### Prerequisites

- CUDA toolkit with nvcc (see [WSL2 GPU Setup](wsl2-gpu-setup.md))
- Downloaded model (see [WSL2 GPU Setup](wsl2-gpu-setup.md))

## Configuration

### The Startup Command

```bash
export CUDA_HOME=/usr/local/cuda
export PATH=$HOME/.local/bin:$CUDA_HOME/bin:$PATH

vllm serve <model-path> \
  --port 8000 \
  --enable-prefix-caching \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_xml \
  --served-model-name default \
  --max-model-len 65536 \
  --gpu-memory-utilization 0.93 \
  --enable-expert-parallel
```

### Flag Reference

#### Required Flags

| Flag | Value | Purpose |
|------|-------|---------|
| `--port` | `8000` | HTTP port for API |
| `--enable-auto-tool-choice` | (no value) | Enables native tool calling |
| `--tool-call-parser` | `qwen3_xml` | Parser for Qwen3-Coder tool calls. **Must be `qwen3_xml`** |
| `--served-model-name` | `default` | Model alias for API requests |

#### Performance Flags

| Flag | Value | Purpose |
|------|-------|---------|
| `--enable-prefix-caching` | (no value) | Cache shared prompt prefixes across requests |
| `--enable-expert-parallel` | (no value) | 15-20% speed boost for MoE models (Qwen3-30B) |
| `--max-model-len` | `65536` | Max context length in tokens |
| `--gpu-memory-utilization` | `0.93` | Fraction of total GPU memory to use |

#### Flags to NEVER Use

| Flag | Why |
|------|-----|
| `--reasoning-parser qwen3` | All output goes to thinking blocks. Claude Code ignores thinking and hangs. |
| `--tool-call-parser hermes` | Broken for Qwen3-Coder. Tool calls appear as raw text, not parsed into tool_use blocks. |
| `--kv-cache-dtype fp8_e4m3` | 10x slower on WSL2 (RTX 5090 FP8 tensor cores not exposed through dxgkrnl). |
| `--enforce-eager` | Disables CUDA graphs. 2-3x slower for batch size 1. |

### Choosing max-model-len

Context length directly impacts speed and VRAM usage.

| max-model-len | tok/s (500 tok output) | VRAM status (RTX 5090) |
|---------------|------------------------|------------------------|
| 32,768 | 177 | OK — fastest |
| **65,536** | **139** | **OK — recommended balance** |
| 100,000 | 26 | OK but speed collapses for long outputs |
| 131,072 | — | FAIL (out of VRAM without fp8) |

**Recommendation:** Use 65,536 for production. Use 32,768 if you need maximum speed and your prompts fit.

Speed collapses at 100K because KV cache fills almost all available VRAM, forcing slower memory access. This is not a bug — it's a VRAM constraint.

### Choosing gpu-memory-utilization

This is the fraction of **total** GPU memory vLLM is allowed to use. On Windows with WSL2:

- Total VRAM: 31.84 GiB (RTX 5090)
- Windows DWM (display compositor) uses: ~1.6 GiB
- Actually available: ~30.2 GiB

| Value | Requested | Status |
|-------|-----------|--------|
| 0.90 | 28.66 GiB | OK (default, conservative) |
| 0.93 | 29.61 GiB | OK (recommended) |
| 0.94 | 29.93 GiB | OK (tight) |
| 0.95 | 30.25 GiB | FAIL (exceeds available) |

Use `0.93` as default. Increase to `0.94` only if you need more KV cache space for longer context.

## API Endpoints

vLLM 0.19+ exposes these relevant endpoints:

| Endpoint | Protocol | Purpose |
|----------|----------|---------|
| `/v1/messages` | Anthropic Messages | Used by `claude --bare -p` |
| `/v1/chat/completions` | OpenAI Chat | Standard OpenAI-compatible |
| `/v1/models` | OpenAI | List available models |
| `/health` | GET | Health check (returns 200 when ready) |

The Anthropic Messages endpoint is what makes vLLM work directly with Claude Code — no proxy needed.

## Starting from PowerShell

From Windows PowerShell, start vLLM in WSL:

```powershell
wsl -e bash -c "export CUDA_HOME=/usr/local/cuda && export PATH=`$HOME/.local/bin:`$CUDA_HOME/bin:`$PATH && vllm serve /home/hanf/models/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit --port 8000 --enable-prefix-caching --enable-auto-tool-choice --tool-call-parser qwen3_xml --served-model-name default --max-model-len 65536 --gpu-memory-utilization 0.93 --enable-expert-parallel"
```

Wait for `Uvicorn running on http://0.0.0.0:8000` or check health:
```powershell
curl http://localhost:8000/health
```

## Startup Time

First start (cold cache):
| Phase | Duration |
|-------|----------|
| Model loading | ~20s |
| torch.compile | ~15s |
| CUDA graph profiling | ~10s |
| **Total** | **~45-60s** |

Subsequent starts (warm cache):
| Phase | Duration |
|-------|----------|
| Model loading | ~10s |
| torch.compile (cached) | ~3s |
| CUDA graph profiling | ~10s |
| **Total** | **~20-30s** |

The torch.compile cache is stored in `~/.cache/vllm/`. Clearing this cache forces a cold start.

## Testing the Server

### Health check
```bash
curl http://localhost:8000/health
```

### Simple message (Anthropic format)
```bash
curl http://localhost:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: dummy" \
  -d '{"model": "default", "max_tokens": 100, "messages": [{"role": "user", "content": "Hello"}]}'
```

### Streaming test
```bash
curl http://localhost:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: dummy" \
  -d '{"model": "default", "max_tokens": 50, "messages": [{"role": "user", "content": "Say hi"}], "stream": true}'
```

You should see SSE events with `content_block_delta` of type `text_delta`.

## Stopping vLLM

In the WSL terminal: `Ctrl+C`

From PowerShell:
```powershell
wsl -e bash -c "pkill -f 'vllm serve'"
```

## Remote Access

vLLM binds to `0.0.0.0` by default — accessible from other machines on the same network.

1. Find the host IP: `ipconfig` in PowerShell → WiFi adapter → IPv4 address
2. On the remote machine, set: `ANTHROPIC_BASE_URL=http://<host-ip>:8000`
3. Ensure Windows Firewall allows inbound TCP on port 8000

This enables running vLLM on a powerful desktop while using Claude Code on a laptop.
