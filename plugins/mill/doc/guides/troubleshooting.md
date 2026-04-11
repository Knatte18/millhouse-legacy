# Troubleshooting

Every error we hit during setup, in the order we hit them. Each entry has the exact error message, cause, and fix.

## WSL2 / CUDA

### `error: externally-managed-environment`

**When:** Running `pip install` in WSL2 Debian Trixie (Python 3.13).

**Full error:**
```
× This environment is externally managed
╰─> To install Python packages system-wide, try apt install python3-xyz
```

**Cause:** PEP 668 — Debian blocks system-wide pip installs to protect the system Python.

**Fix:** Use a virtual environment:
```bash
sudo apt install -y python3.13-venv
python3 -m venv /home/$USER/venvs/llm
source /home/$USER/venvs/llm/bin/activate
pip install <package>
```

### `The virtual environment was not created successfully because ensurepip is not available`

**When:** Running `python3 -m venv` without the venv package.

**Fix:**
```bash
sudo apt install -y python3.13-venv
```

### `Error: Package 'nvidia-cuda-toolkit' has no installation candidate`

**When:** Trying to install CUDA toolkit via apt on Debian Trixie.

**Cause:** NVIDIA's apt repository uses SHA1-signed GPG keys. Debian Trixie (2026+) rejects SHA1 signatures:
```
Policy rejected non-revocation signature because: SHA1 is not considered secure since 2026-02-01
```

**Fix:** Install via NVIDIA runfile instead of apt:
```bash
sudo apt install -y curl
curl -fSL -o /tmp/cuda.run https://developer.download.nvidia.com/compute/cuda/12.9.0/local_installers/cuda_12.9.0_575.51.03_linux.run
mkdir -p /home/$USER/tmp
sudo sh /tmp/cuda.run --toolkit --silent --override --tmpdir=/home/$USER/tmp
```

### `Extraction failed. Ensure there is enough space in /tmp`

**When:** Running the CUDA installer runfile.

**Cause:** WSL2's `/tmp` is a tmpfs with limited size (~16 GB). The 5.5 GB runfile plus extraction needs more space.

**Fix:** Use `--tmpdir` pointing to a real filesystem:
```bash
mkdir -p /home/$USER/tmp
sudo sh /tmp/cuda.run --toolkit --silent --override --tmpdir=/home/$USER/tmp
```

### `bash: huggingface-cli: command not found`

**When:** Trying to download a model after installing huggingface-hub.

**Cause:** `huggingface-cli` is deprecated. The new command is `hf`.

**Fix:**
```bash
/home/$USER/venvs/llm/bin/hf download <model-name> --local-dir /home/$USER/models/<model-name>
```

### `Warning: huggingface-cli is deprecated and no longer works. Use hf instead.`

**When:** Running `huggingface-cli` after installing huggingface-hub 1.10+.

**Fix:** Use `hf` command instead. See above.

### `Error: Model 'Qwen/Qwen3-Coder-30B-A3B-Instruct-AWQ' not found`

**When:** Downloading a model from HuggingFace.

**Cause:** There is no official AWQ quant from Qwen. The AWQ versions are community-made.

**Fix:** Use a community quant:
```bash
hf download cpatonn/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit --local-dir /home/$USER/models/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit
```

Other options: `stelterlab/Qwen3-Coder-30B-A3B-Instruct-AWQ`, `QuantTrio/Qwen3-Coder-30B-A3B-Instruct-AWQ`.

## vLLM Startup Errors

### `bash: vllm: command not found`

**When:** Running `vllm serve` in WSL.

**Cause:** vLLM was installed via `pip install vllm` (or `pip install --break-system-packages vllm`), which puts the binary in `~/.local/bin/`. This directory is not in PATH by default.

**Fix:**
```bash
export PATH=$HOME/.local/bin:$PATH
```

Or add it permanently to your shell profile (`~/.bashrc` or `~/.profile`):
```bash
echo 'export PATH=$HOME/.local/bin:$PATH' >> ~/.bashrc
```

The `start-qwen.ps1` script handles this automatically.

### `RuntimeError: Could not find nvcc and default cuda_home='/usr/local/cuda' doesn't exist`

**When:** vLLM starting, during FlashInfer JIT compilation.

**Cause:** CUDA toolkit not installed, or `CUDA_HOME` not set.

**Fix:**
```bash
export CUDA_HOME=/usr/local/cuda
export PATH=$CUDA_HOME/bin:$PATH
```

If `/usr/local/cuda` doesn't exist, install the CUDA toolkit (see WSL2 section above).

### `Unknown vLLM environment variable detected: VLLM_ATTENTION_BACKEND`

**When:** Setting `VLLM_ATTENTION_BACKEND` env var with vLLM 0.19.

**Cause:** vLLM 0.19 removed this environment variable. Old guides still reference it.

**Fix:** There is no env var to control the attention backend in 0.19. If FlashInfer fails, fix the root cause (install nvcc) rather than trying to switch backends.

### `ValueError: Free memory on device cuda:0 (30.2/31.84 GiB) is less than desired GPU memory utilization (0.95, 30.25 GiB)`

**When:** Starting vLLM with `--gpu-memory-utilization 0.95`.

**Cause:** Windows DWM (display compositor) uses ~1.6 GiB VRAM. Only ~30.2 GiB is actually available out of 31.84 GiB total.

**Fix:** Use `--gpu-memory-utilization 0.93` (or max `0.94`):
```bash
vllm serve ... --gpu-memory-utilization 0.93
```

### `ValueError: To serve at least one request with the model's max seq len (262144), 12.0 GiB KV cache is needed, which is larger than the available KV cache memory (10.91 GiB)`

**When:** Starting vLLM without `--max-model-len` (defaults to model's full 262K context).

**Cause:** The model supports 262K context, but with fp16 KV cache, there's not enough VRAM.

**Fix:** Set a lower context length:
```bash
vllm serve ... --max-model-len 65536
```

Maximum usable values without fp8:
- 65,536 — recommended (139 tok/s)
- 100,000 — works but speed collapses to 26 tok/s
- 131,072 — fails (needs 12.0 GiB, only 11.88 available)

### `Using 'pin_memory=False' as WSL is detected. This may slow down the performance.`

**This is a warning, not an error.** WSL2 doesn't support pinned memory for GPU transfers. It causes slightly slower CPU↔GPU data transfer. No fix — WSL2 limitation. Native Linux would not have this issue.

## vLLM Runtime Errors

### `Error with model error=ErrorInfo(message='The model "claude-sonnet-4-6" does not exist.')`

**When:** Claude Code sends a request to vLLM.

**Cause:** Claude Code sends Claude model names (`claude-sonnet-4-6`), but vLLM only has `default`.

**Fix:** Set model mapping environment variables before calling `claude`:
```powershell
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = "default"
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = "default"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = "default"
```

### `max context length is 32768 tokens. However, you requested 32000 output tokens and your prompt contains at least 769 input tokens`

**When:** Claude Code sends a request with high `max_tokens`.

**Cause:** Claude Code defaults to requesting 32000 output tokens. With a 32K context limit, prompt + output exceeds the limit.

**Fix:** Use `--max-model-len 65536` or higher. 64K accommodates Claude Code's 32K output request plus prompt.

## Claude Code Issues

### `claude -p` hangs indefinitely (no output)

**When:** Running `claude -p` with `ANTHROPIC_BASE_URL` pointing at vLLM.

**Cause:** Claude Code tries to contact api.anthropic.com for MCP configuration, hooks, plugin sync. These requests go to vLLM (via the redirected base URL), which doesn't understand them.

**Fix:** Use `--bare`:
```powershell
claude --bare -p "Say hi" --model default
```

### `Not logged in · Please run /login`

**When:** Running `claude --bare -p` after changing directory or opening a new PowerShell.

**Cause:** Environment variables are not set in this PowerShell session.

**Fix:** Set all env vars again:
```powershell
$env:ANTHROPIC_BASE_URL = "http://localhost:8000"
$env:ANTHROPIC_API_KEY = "dummy"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = "default"
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = "default"
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = "default"
```

### Claude Code shows no output but vLLM shows `200 OK`

**When:** Running `claude -p` (without `--bare`). vLLM log shows successful responses.

**Possible causes:**
1. **Thinking blocks:** If `--reasoning-parser qwen3` is set on vLLM, all output goes to thinking blocks. Claude Code ignores thinking and shows nothing. Fix: restart vLLM without `--reasoning-parser`.
2. **Streaming format mismatch:** Verify with direct curl that response contains `text_delta` (not `thinking_delta`):
   ```powershell
   Invoke-RestMethod -Uri "http://localhost:8000/v1/messages" -Method Post -ContentType "application/json" -Headers @{"x-api-key"="dummy"} -Body '{"model":"default","max_tokens":50,"messages":[{"role":"user","content":"Say hi"}],"stream":true}'
   ```
   If you see `thinking_delta` instead of `text_delta`, the reasoning parser is active.

### Tool use: model generates tool call as text instead of tool_use block

**When:** `claude --bare -p` with tool use. Model outputs `<function=Read><parameter=file_path>...` as plain text.

**Cause:** Wrong tool call parser. `--tool-call-parser hermes` generates Hermes-format tool calls that vLLM doesn't translate to Anthropic tool_use blocks.

**Fix:** Restart vLLM with `--tool-call-parser qwen3_xml`.

### Tool use: model calls Read but Claude Code exits after first turn

**When:** `claude --bare -p` returns after the model's first response (which is a tool call), without executing the tool.

**Cause:** `--max-turns` not set or set to 1. Claude Code defaults to 1 turn in print mode.

**Fix:**
```powershell
claude --bare -p "Read CLAUDE.md and summarize it" --model default --max-turns 5
```

## Performance Issues

### vLLM: 20 tok/s instead of expected 140+

**Cause:** `--kv-cache-dtype fp8_e4m3` is set. On WSL2 with RTX 5090, FP8 tensor cores are not exposed through dxgkrnl. FP8 operations are emulated in software — 10x slower.

**Fix:** Remove `--kv-cache-dtype fp8_e4m3` from the vLLM command. Use default fp16 KV cache. Accept 64K max context instead of 200K.

### vLLM: 57 tok/s with `--enforce-eager`

**Cause:** `--enforce-eager` disables CUDA graphs. For single-user (batch size 1) inference, CUDA graphs provide significant speedup.

**Fix:** Remove `--enforce-eager`. Let vLLM use CUDA graphs (default behavior).

### Ollama: 200 tok/s in benchmarks but 26 tok/s in practice

**Cause:** Most benchmarks use Ollama's default `num_ctx` of 2048 tokens. At realistic context sizes (32K+), Ollama drops to 26 tok/s.

**Fix:** This is not a bug — it's expected behavior. To verify, check what `num_ctx` was used:
```bash
# In the response JSON, check if load_duration is present — indicates model was reloaded for new num_ctx
```

### vLLM: speed collapses at 100K context

**Cause:** At 100K, KV cache uses almost all available VRAM (~10 of 12 GiB available). Memory access patterns become slower when VRAM is near capacity.

**Fix:** Use 64K max-model-len. If you need 100K+, wait for WSL2 FP8 support (dxgkrnl update) which halves KV cache VRAM usage.

## GPU Sharing

### Both vLLM and Ollama are slow / crashing

**Cause:** Both are running simultaneously and fighting for GPU memory.

**Fix:** Only one can run at a time. Kill the other:
```powershell
# Kill Ollama (Windows)
Stop-Process -Name "ollama" -Force -ErrorAction SilentlyContinue

# Kill vLLM (WSL)
wsl -e bash -c "pkill -f 'vllm serve'"
```

Verify only one is running:
```powershell
# Check vLLM
curl http://localhost:8000/health

# Check Ollama
curl http://localhost:11434/api/tags
```

Only one should respond.
