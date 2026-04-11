# WSL2 GPU Setup Guide

How to set up WSL2 on Windows 11 for local LLM inference with an NVIDIA GPU. Covers CUDA toolkit, Python environments, and model downloads.

## Prerequisites

- Windows 11 with WSL2 enabled
- NVIDIA GPU with recent drivers (595+)
- WSL2 distribution installed (Debian Trixie or Ubuntu)

Verify GPU access from WSL:
```bash
nvidia-smi
```
You should see your GPU listed with driver version and CUDA version.

## CUDA Toolkit Installation

vLLM's FlashInfer attention backend requires `nvcc` for JIT compilation. The CUDA toolkit is not installed by default in WSL2.

### Why not apt?

On Debian Trixie (2026+), NVIDIA's apt repository uses SHA1-signed GPG keys, which Debian rejects:
```
Policy rejected non-revocation signature because: SHA1 is not considered secure since 2026-02-01
```

The `nvidia-cuda-toolkit` package may also not have an installation candidate.

### Install via NVIDIA Runfile (recommended)

```bash
sudo apt install -y curl
curl -fSL -o /tmp/cuda.run https://developer.download.nvidia.com/compute/cuda/12.9.0/local_installers/cuda_12.9.0_575.51.03_linux.run
mkdir -p /home/$USER/tmp
sudo sh /tmp/cuda.run --toolkit --silent --override --tmpdir=/home/$USER/tmp
```

Notes:
- The runfile is ~5.5 GB — download takes time
- `--tmpdir` is needed because `/tmp` is a tmpfs with limited space in WSL2
- `--toolkit` installs only the toolkit, not drivers (WSL uses Windows drivers)
- `--override` skips the driver version check

### Verify

```bash
/usr/local/cuda/bin/nvcc --version
```

Should print CUDA compilation tools version.

### Set Environment

Add to your shell profile or run before starting vLLM:
```bash
export CUDA_HOME=/usr/local/cuda
export PATH=$CUDA_HOME/bin:$PATH
```

## Python Environment

WSL2 Debian Trixie uses Python 3.13 with PEP 668 (externally-managed-environment). System-wide pip installs are blocked:
```
error: externally-managed-environment
```

### Create a Virtual Environment

```bash
sudo apt install -y python3.13-venv
python3 -m venv /home/$USER/venvs/llm
```

Activate:
```bash
source /home/$USER/venvs/llm/bin/activate
```

This venv is used for support tools (huggingface-cli, nvidia-cuda-nvcc). vLLM itself may be installed system-wide via pip with `--break-system-packages` or in a separate venv.

## Model Downloads

### Install HuggingFace CLI

The old `huggingface-cli` command is deprecated. Use `hf`:

```bash
source /home/$USER/venvs/llm/bin/activate
pip install 'huggingface-hub[cli]'
```

### Download a Model

Example: Qwen3-Coder-30B AWQ 4-bit quantized:
```bash
/home/$USER/venvs/llm/bin/hf download cpatonn/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit \
  --local-dir /home/$USER/models/Qwen3-Coder-30B-A3B-Instruct-AWQ-4bit
```

This downloads ~16 GB to the WSL filesystem. Store models on the Linux filesystem, not `/mnt/c/` — the Windows filesystem translation adds latency.

### Model Storage

Keep models in `/home/$USER/models/`. This path is on the WSL ext4 filesystem, which is faster than the Windows NTFS mount.

## Memory Considerations

### VRAM (GPU Memory)

RTX 5090 has 32 GB VRAM. With Qwen3-Coder-30B AWQ 4-bit:
- Model weights: ~17 GiB
- CUDA graphs: ~0.9 GiB
- PyTorch overhead: ~2-3 GiB
- Available for KV cache: ~10-12 GiB
- Windows DWM (display compositor): ~1.6 GiB (always reserved)

### System RAM

WSL2 mirrors model data in system RAM during loading. With 64 GB RAM this is fine. The VmmemWSL process in Task Manager shows WSL's total memory usage — expect ~25 GB during model loading, dropping after startup.

## WSL2 Limitations

| Limitation | Impact |
|-----------|--------|
| FP8 tensor cores not exposed (dxgkrnl) | `--kv-cache-dtype fp8_e4m3` is 10x slower — emulated in software |
| `pin_memory=False` | Slower CPU-GPU data transfer vs native Linux |
| Windows DWM uses ~1.6 GiB VRAM | Limits `--gpu-memory-utilization` to ~0.94 |
| tmpfs size limit | Need `--tmpdir` for CUDA installer |
| NTFS mount is slow | Store models on Linux filesystem, not `/mnt/c/` |

These limitations are eliminated by running native Linux (dual-boot).
