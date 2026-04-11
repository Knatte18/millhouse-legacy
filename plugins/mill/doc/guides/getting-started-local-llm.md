# Getting Started with Local LLM

How to set up a local LLM backend for Millhouse review agents. This guide walks through the full setup from scratch: WSL2, CUDA, model download, vLLM, configuration, and verification.

> For Ollama as an alternative backend, see [Ollama Guide](ollama-guide.md).

## Prerequisites

- NVIDIA GPU (tested on RTX 5090 with 32 GB VRAM; other GPUs may work but are untested)
- Windows 11 with WSL2 enabled
- NVIDIA driver 595+ (check in Device Manager or `nvidia-smi`)
- ~20 GB free disk space in WSL for the model

Verify GPU access from WSL:
```bash
nvidia-smi
```

You should see your GPU listed with driver version and CUDA version. If this fails, install or update your NVIDIA driver from the NVIDIA website.

See [WSL2 GPU Setup](wsl2-gpu-setup.md) for details on hardware requirements and WSL2 limitations.

## CUDA Toolkit

vLLM requires `nvcc` for JIT compilation. Install via the NVIDIA runfile (not apt — see [WSL2 GPU Setup](wsl2-gpu-setup.md#cuda-toolkit-installation) for why).

```bash
sudo apt install -y curl
curl -fSL -o /tmp/cuda.run https://developer.download.nvidia.com/compute/cuda/12.9.0/local_installers/cuda_12.9.0_575.51.03_linux.run
mkdir -p /home/$USER/tmp
sudo sh /tmp/cuda.run --toolkit --silent --override --tmpdir=/home/$USER/tmp
```

Notes:
- The runfile is ~5.5 GB
- `--tmpdir` is needed because `/tmp` is a tmpfs with limited space in WSL2
- `--toolkit` installs only the toolkit, not drivers (WSL uses Windows drivers)
- `--override` skips the driver version check

Verify:
```bash
/usr/local/cuda/bin/nvcc --version
```

Set environment variables (add to your shell profile or run before starting vLLM):
```bash
export CUDA_HOME=/usr/local/cuda
export PATH=$HOME/.local/bin:$CUDA_HOME/bin:$PATH
```

`$HOME/.local/bin` is the default pip user install location — needed for `hf` and `vllm` commands.

## Python Environment

WSL2 Debian Trixie uses PEP 668, which blocks system-wide pip installs. Create a virtual environment:

```bash
sudo apt install -y python3.13-venv
python3 -m venv /home/$USER/venvs/llm
source /home/$USER/venvs/llm/bin/activate
```

See [WSL2 GPU Setup](wsl2-gpu-setup.md#python-environment) for details.

## Model Download

With the venv activated, install the HuggingFace CLI and download the model:

```bash
source /home/$USER/venvs/llm/bin/activate
pip install 'huggingface-hub[cli]'
```

Download Qwen3-Coder-30B AWQ 4-bit (~16 GB):
```bash
hf download cpatonn/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit \
  --local-dir /home/$USER/models/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit
```

Store models on the Linux filesystem (`/home/$USER/models/`), not `/mnt/c/` — the Windows NTFS mount adds latency.

See [WSL2 GPU Setup](wsl2-gpu-setup.md#model-downloads) for more details.

## Install vLLM

With the venv active, install vLLM:

```bash
source /home/$USER/venvs/llm/bin/activate
pip install vllm
```

See [vLLM Guide](vllm-guide.md#installation) for prerequisites and details.

## Configure Millhouse

Edit `_millhouse/config.yaml` in your Millhouse repo. Add or update the `llm-backend` section:

```yaml
llm-backend:
  # Master switch. Set to true to enable alternative backend dispatch.
  enabled: true

  # Which provider to use. Currently supported: vllm
  provider: vllm

  # Fall back to Claude (Agent tool) when the local provider is unavailable.
  fallback-to-claude: true

  vllm:
    # URL where vLLM is listening. Port is extracted from this URL.
    url: http://localhost:8000

    # Model name as configured in vLLM (--served-model-name).
    model-name: default

    # Path to the model directory inside WSL.
    # Replace <username> with your WSL username.
    wsl-model-path: /home/<username>/models/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit

    # Maximum context length in tokens (--max-model-len).
    # 65536 is the recommended balance of speed (139 tok/s) and capacity.
    # See benchmarks.md for speed at other context sizes.
    max-model-len: 65536

    # Fraction of GPU memory vLLM may use (--gpu-memory-utilization).
    # 0.93 is recommended for RTX 5090 (Windows DWM uses ~1.6 GiB).
    # Do not exceed 0.94 on Windows.
    gpu-memory-utilization: 0.93

    # Additional vLLM flags appended to the serve command.
    # These are always included: --enable-prefix-caching,
    # --enable-auto-tool-choice, --tool-call-parser qwen3_xml,
    # --enable-expert-parallel.
    # NEVER add: --reasoning-parser, --kv-cache-dtype fp8_e4m3,
    # --enforce-eager, --tool-call-parser hermes.
    extra-flags: ""
```

Replace `<username>` with your WSL username (run `whoami` in WSL to check).

## Start vLLM

From PowerShell, in your repo root:

```powershell
.\_millhouse\start-qwen.ps1
```

The script reads `_millhouse/config.yaml` automatically, starts vLLM in WSL with the correct flags, and polls the health endpoint until ready.

- First start (cold cache): ~45-60 seconds
- Subsequent starts (warm cache): ~20-30 seconds

See [vLLM Guide](vllm-guide.md#starting-from-powershell) for manual startup and flag details.

## Verify

Three progressive checks. If an earlier check fails, fix it before moving to the next.

### 1. Health check

```bash
curl http://localhost:8000/health
```

Returns empty body with HTTP 200 when vLLM is ready. If this fails, vLLM is not running or not yet ready — wait and retry.

### 2. Test message

```bash
curl http://localhost:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: dummy" \
  -d '{"model": "default", "max_tokens": 100, "messages": [{"role": "user", "content": "Hello"}]}'
```

You should get a JSON response with the model's reply. If this fails but health passes, check model name (`default` must match `--served-model-name`).

### 3. Spawn-agent test

Prerequisites:
- vLLM must be running (started above)
- `llm-backend.enabled` must be `true` in `_millhouse/config.yaml`

From PowerShell, in your repo root:

```powershell
"Say hello" | Out-File -Encoding utf8 test-prompt.txt
.\_millhouse\spawn-agent.ps1 -PromptFile test-prompt.txt -MaxTurns 1 -WorkDir $PWD
```

Exit code 0 means the full pipeline works: config was read, vLLM was health-checked, and `claude --bare` successfully used the local model.

If exit code 2: check that vLLM is running AND that `enabled: true` is set in config — both are required. See [Troubleshooting](troubleshooting.md) for other errors.

Clean up the test file:
```powershell
Remove-Item test-prompt.txt
```

## Stop vLLM

From PowerShell:

```powershell
.\_millhouse\stop-qwen.ps1
```

See [vLLM Guide](vllm-guide.md#stopping-vllm) for manual stop methods.

## Troubleshooting

See [Troubleshooting](troubleshooting.md) for the full list. Common issues:

| Problem | Cause | Fix |
|---------|-------|-----|
| `vllm: command not found` | `~/.local/bin` not in PATH | Run `export PATH=$HOME/.local/bin:$PATH` (or add to `~/.bashrc`) |
| `nvcc not found` | CUDA toolkit not installed | Run the CUDA runfile installer above |
| `gpu-memory-utilization exceeds available` | Value too high for your GPU | Lower to 0.90 in config.yaml |
| Health check times out | vLLM still starting or crashed | Check WSL terminal for errors; first start takes 45-60s |

## Next Steps

- [Benchmarks](benchmarks.md) — performance data and tuning recommendations
- [vLLM Guide](vllm-guide.md) — flag reference, context length tuning, remote access
- [Claude Code Local LLM](claude-code-local-llm.md) — environment variables, `--bare` flag, tool use details
