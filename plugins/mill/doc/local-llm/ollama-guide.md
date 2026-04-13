# Ollama operational guide

Operational reference for running Ollama on Windows + RTX 5090 for local LLM
inference. This is the **how to do it** companion to `benchmarks.md` (which
covers the **why** and **which model**).

For context on why local inference is interesting at all (and where it falls
short), see `README.md` and `lessons-vllm-tooluse.md`.

## Why Ollama (and not vLLM)

After Pass 1 (`lessons-vllm-tooluse.md`) abandoned vLLM, Pass 2 standardised
on Ollama for all local inference work:

- **Fast startup** (~6-8s vs vLLM's 45-60s)
- **Simple setup** — one installer, no WSL, no CUDA toolkit, no venv
- **Native thinking mode** — Qwen3.5 and DeepSeek R1 variants use chain-of-thought reasoning
- **Good speed** — 133-150 tok/s for 30-35B models on RTX 5090
- **No GPU compilation issues** — no FlashInfer, no nvcc required
- **OpenAI-compatible API** — works with most tooling
- **Works well for bulk-mode dispatch** — pre-assembled prompts, no tool use round trips

## Limitation: No Parallel Reviews on Single GPU

A 30B model at Q4_K_M takes ~17-20 GB VRAM, plus 6-12 GB for KV cache at 64-96K context.
On a 32 GB card this leaves no room for a second instance — Ollama will queue concurrent
requests sequentially.

**Implication for ensemble strategies:** running N parallel reviewers locally takes N × the
single-review wall clock. For comparison, cloud providers (Gemini Pro, Sonnet) handle the
parallelism remotely and return all N reviews in roughly single-review wall clock time.

If your review strategy depends on parallel ensemble (e.g., 3 × non-deterministic Gemini Pro
runs to maximise coverage), local Ollama is not a drop-in replacement on single-GPU hardware.
It works fine for sequential per-round reviews — just don't expect concurrent throughput.

## Installation

Download from [ollama.com](https://ollama.com) and run the installer. Ollama runs as a Windows service on port 11434.

### Verify installation

```powershell
ollama --version
curl http://localhost:11434/api/tags
```

## Recommended Models

### For code review (tested on mill-go SKILL.md review task)

| Model | Size | Time | Quality | Recommendation |
|-------|------|------|---------|----------------|
| `qwen3-coder:30b` | 18.6 GB | 15s | Overfladisk — 3 critical findings | Fast first-pass screening |
| `qwen3.5:35b-a3b` | 23.9 GB | 35s | **Sonnet-level — 5 critical findings** | **Primary review model** |
| `qwen3.5:27b` | 17.4 GB | ~30s | Solid | Balanced option |
| `deepseek-r1:32b` | ~20 GB | TBD | Best reasoning | Best for complex analysis |
| `deepseek-coder-v2:16b` | ~10 GB | ~25s | 92.7% HumanEval | Best for code generation tasks |

### Pulling models

```powershell
ollama pull qwen3.5:35b-a3b        # Primary reviewer (recommended)
ollama pull deepseek-r1:32b        # Reasoning-heavy review
ollama pull qwen3-coder:30b        # Fast screening
```

Models are stored in `C:\Users\<user>\.ollama\models\`.

## Context Size — CRITICAL

**Default `num_ctx` is 2048 tokens — UNUSABLE for real work.** Always set explicitly.

### Per-request
```json
{
  "model": "qwen3.5:35b-a3b",
  "options": {
    "num_ctx": 32768
  }
}
```

**WARNING:** Changing `num_ctx` forces a model reload (~6-8s). Keep it consistent across requests for a session.

### Permanent (via custom Modelfile)

Create a fixed-context variant:

```powershell
# Create a Modelfile
@"
FROM qwen3.5:35b-a3b
PARAMETER num_ctx 32768
"@ | Out-File -Encoding ASCII modelfile-32k.txt

# Build the custom model
ollama create qwen3.5:35b-32k -f modelfile-32k.txt
```

Then use `qwen3.5:35b-32k` — no reload on every request.

### Context size vs speed (RTX 5090, Qwen3-Coder-30B)

| num_ctx | tok/s |
|---------|-------|
| 2,048 (default) | 177 (unusable — too small) |
| 8,192 | ~52 |
| 16,384 | ~26 |
| 32,768 | 26 |
| 65,536 | 26 |
| 100,000 | 24 |
| 200,000 | 35 (anomaly — needs retest) |

**Recommendation:** Use **32,768** for reviews. Large enough for any practical prompt, speed is acceptable.

## Thinking Mode

Qwen3.5 and DeepSeek R1 support chain-of-thought reasoning via thinking mode. `qwen3-coder:30b` does NOT support this (it's code-only trained).

### Enable via API

```json
{
  "model": "qwen3.5:35b-a3b",
  "think": true,
  "messages": [...]
}
```

### Enable via prompt tag

Add `/think` at the end of the user message to force deeper reasoning.

### Expected performance with thinking (recommended)

```json
{
  "options": {
    "temperature": 0.6,
    "top_p": 0.95,
    "top_k": 20,
    "num_ctx": 32768,
    "num_predict": 4000
  }
}
```

**Thinking mode significantly improves quality for review tasks:**
- qwen3-coder:30b (no thinking): 3 critical findings, overfladisk
- qwen3.5:35b-a3b (thinking): 5 critical findings, Sonnet-level depth

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/chat` | Chat completion (preferred for this use case) |
| `POST /api/generate` | Text completion |
| `GET /api/tags` | List installed models |
| `POST /api/show` | Model details |
| `POST /api/pull` | Download model |
| `POST /api/embeddings` | Get embeddings |

### Response timing fields (useful for benchmarking)

- `eval_count`: output tokens generated
- `eval_duration`: generation time (nanoseconds)
- `prompt_eval_count`: input tokens
- `prompt_eval_duration`: prompt processing time
- `load_duration`: model load time (0 if already loaded)
- `total_duration`: total wall time

**Calculate tok/s:** `eval_count / (eval_duration / 1e9)`

## Network Exposure (LAN / WiFi access)

By default, Ollama binds to `127.0.0.1:11434` (localhost only). To access from another machine (e.g., laptop connecting to desktop over WiFi), expose it on the network.

### Step 1: Set OLLAMA_HOST environment variable

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0:11434", "User")
```

This binds to all network interfaces. For more security, use a specific IP like your WiFi IP.

### Step 2: Restart Ollama

Quit from the system tray icon and start it again. Or:

```powershell
Stop-Process -Name ollama -Force
ollama serve
```

### Step 3: Open Windows Firewall

Run as **Administrator**:

```powershell
New-NetFirewallRule -DisplayName "Ollama" -Direction Inbound -Protocol TCP -LocalPort 11434 -Action Allow
```

### Step 4: Find your desktop's IP

```powershell
ipconfig | Select-String "IPv4"
```

Look for the WiFi adapter's IPv4 address (e.g., `192.168.1.42`).

### Step 5: Access from another machine

Change API calls from `http://localhost:11434` to `http://<desktop-ip>:11434`.

Test from laptop:
```powershell
curl http://192.168.1.42:11434/api/tags
```

## Security Warning

**Ollama has no authentication by default.** Anyone on the network can use your models. Mitigations:

1. **Only expose on trusted home network** — never on a public network
2. **Use OLLAMA_ORIGINS** to restrict which origins can call the API:
   ```powershell
   [Environment]::SetEnvironmentVariable("OLLAMA_ORIGINS", "http://192.168.1.*", "User")
   ```
3. **Bind to specific IP** instead of `0.0.0.0`:
   ```powershell
   [Environment]::SetEnvironmentVariable("OLLAMA_HOST", "192.168.1.42:11434", "User")
   ```
4. **Consider a reverse proxy** (nginx, Caddy) with auth if exposing more broadly

## Tool Calling

Ollama supports tool calling via OpenAI-compatible function calling format. Qwen3-Coder has native tool calling.

**Known issues:**
- Qwen models sometimes print tool calls as text instead of executing them
- Multi-turn tool use can break in smaller models
- Format mismatches between Hermes and XML styles

**Recommendation for this project:** Use **bulk-mode dispatch** — pre-assemble all context in the prompt, don't use multi-turn tool use. This is faster and more reliable.

## Using with Claude Code

Ollama does NOT implement the Anthropic Messages API. To use with `claude --bare -p`, you need **LiteLLM** as a translation proxy.

However, for this project we prefer **direct API calls** from PowerShell — no proxy, no `claude -p` round trips. Pre-assemble the prompt, POST to `/api/chat`, parse the response.

Example (PowerShell):
```powershell
$body = @{
  model = "qwen3.5:35b-a3b"
  messages = @(@{role="user"; content=$prompt})
  stream = $false
  think = $true
  options = @{ num_ctx = 32768; num_predict = 4000 }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri "http://localhost:11434/api/chat" `
  -Method Post -ContentType "application/json" -Body $body
```

## GPU Sharing with vLLM

vLLM (WSL) and Ollama (Windows) cannot run simultaneously — both need the full GPU. Kill one before starting the other:

```powershell
# Kill Ollama before starting vLLM
Stop-Process -Name "ollama" -Force -ErrorAction SilentlyContinue

# Kill vLLM (running in WSL) before using Ollama
wsl -e bash -c "pkill -f 'vllm serve'"
```

## Startup Time

| Event | Duration |
|-------|----------|
| Model load (first time, cold) | ~6-8s |
| Model load (after num_ctx change) | ~6-8s |
| Model already loaded | 0s |
| Subsequent requests | <200ms overhead |

Ollama is significantly faster to start than vLLM (~7s vs 45-60s).

## Troubleshooting

### `model does not support thinking`

The model wasn't trained for chain-of-thought. Use a thinking-capable variant:
- `qwen3.5:35b-a3b` ✅
- `qwen3.5:27b` ✅
- `deepseek-r1:32b` ✅
- `qwen3-coder:30b` ❌ (code-only training)

### Speed is slow (<50 tok/s)

Check:
1. `num_ctx` — larger context = slower. Use 32K not 200K unless needed.
2. vLLM running in WSL — kill it.
3. Other GPU-heavy apps — close them.
4. Model not loaded in GPU — first request after idle has load delay.

### Out of VRAM

RTX 5090 has 32 GB. Models using fp16 KV cache can fill VRAM fast. Solutions:
1. Smaller `num_ctx`
2. Smaller model (Q4 quantization)
3. Close other apps using GPU
