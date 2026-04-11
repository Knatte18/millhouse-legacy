# start-qwen.ps1 — Start vLLM in WSL with Qwen model.
# Reads llm-backend.vllm settings from _millhouse/config.yaml,
# kills any existing vLLM/Ollama process, starts vLLM in the background,
# and polls the health endpoint until ready.

$ErrorActionPreference = "Stop"

# --- Resolve config ---
$ConfigPath = Join-Path $PWD "_millhouse/config.yaml"
if (-not (Test-Path $ConfigPath)) {
    Write-Error "_millhouse/config.yaml not found. Run mill-setup first."
    exit 1
}

$ConfigLines = Get-Content $ConfigPath -Encoding UTF8

# --- Parse llm-backend.vllm settings ---
$InVllmBlock = $false
$Url = "http://localhost:8000"
$ModelName = "default"
$WslModelPath = ""
$MaxModelLen = "65536"
$GpuMemUtil = "0.93"
$ExtraFlags = ""

foreach ($line in $ConfigLines) {
    if ($line -match '^\s*vllm:\s*$') {
        $InVllmBlock = $true
        continue
    }
    if ($InVllmBlock) {
        # Exit block on non-indented line or new top-level key
        if ($line -match '^\S') {
            $InVllmBlock = $false
            continue
        }
        if ($line -match '^\s+url:\s*(.+)$') { $Url = $Matches[1].Trim() }
        if ($line -match '^\s+model-name:\s*(.+)$') { $ModelName = $Matches[1].Trim() }
        if ($line -match '^\s+wsl-model-path:\s*(.+)$') { $WslModelPath = $Matches[1].Trim() }
        if ($line -match '^\s+max-model-len:\s*(.+)$') { $MaxModelLen = $Matches[1].Trim() }
        if ($line -match '^\s+gpu-memory-utilization:\s*(.+)$') { $GpuMemUtil = $Matches[1].Trim() }
        if ($line -match '^\s+extra-flags:\s*"?(.*?)"?\s*$') { $ExtraFlags = $Matches[1].Trim() }
    }
}

if (-not $WslModelPath) {
    Write-Error "llm-backend.vllm.wsl-model-path not set in config."
    exit 1
}

# --- Verify model exists in WSL ---
$ModelCheck = wsl -e bash -c "test -d '$WslModelPath' && echo 'ok' || echo 'missing'" 2>$null
if ($ModelCheck -ne "ok") {
    Write-Error "Model not found in WSL at: $WslModelPath"
    exit 1
}

# --- Extract port from URL ---
try {
    $Uri = [System.Uri]$Url
    $Port = $Uri.Port
    if ($Port -le 0) { $Port = 8000 }
} catch {
    Write-Error "Invalid URL in config: $Url"
    exit 1
}

$HealthUrl = "$Url/health"
$VllmLog = "/tmp/vllm.log"

Write-Host "Model:   $WslModelPath"
Write-Host "URL:     $Url"
Write-Host "Context: $MaxModelLen tokens"
Write-Host "GPU mem: $GpuMemUtil"
Write-Host "Log:     wsl: $VllmLog"
Write-Host ""

# --- Kill existing GPU processes ---
Write-Host "Stopping any existing vLLM process..."
wsl -e bash -c "pkill -f 'vllm serve'" 2>$null

Write-Host "Stopping Ollama (GPU sharing conflict)..."
Stop-Process -Name "ollama" -Force -ErrorAction SilentlyContinue 2>$null
Stop-Process -Name "ollama_llama_server" -Force -ErrorAction SilentlyContinue 2>$null

Start-Sleep -Seconds 2

# --- Build vLLM flags ---
$VllmFlags = "--port $Port --enable-prefix-caching --enable-auto-tool-choice --tool-call-parser qwen3_xml --served-model-name $ModelName --max-model-len $MaxModelLen --gpu-memory-utilization $GpuMemUtil --enable-expert-parallel"

if ($ExtraFlags) {
    $VllmFlags += " $ExtraFlags"
}

# --- Write startup script to Windows temp ---
# Writing to the Windows filesystem avoids PowerShell-to-bash quoting issues.
# WSL reads the script via /mnt/c/.
$TempPath = Join-Path $env:TEMP "start-vllm.sh"
$ScriptLines = @(
    "#!/bin/bash",
    "export CUDA_HOME=/usr/local/cuda",
    "export PATH=`$HOME/.local/bin:`$CUDA_HOME/bin:`$PATH",
    "exec vllm serve $WslModelPath $VllmFlags"
)
[IO.File]::WriteAllText($TempPath, ($ScriptLines -join [char]10) + [char]10)

# Convert Windows path to WSL /mnt/ path
$Drive = $TempPath.Substring(0, 1).ToLower()
$WslScriptPath = "/mnt/$Drive" + $TempPath.Substring(2).Replace('\', '/')

# --- Start vLLM as daemon in WSL ---
Write-Host "Starting vLLM..."
wsl -e bash -c "nohup bash '$WslScriptPath' > $VllmLog 2>&1 & disown; sleep 1"

# --- Poll health endpoint ---
$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$MaxWaitSeconds = 120
$PollInterval = 5
$Ready = $false

Write-Host "Waiting for health endpoint ($HealthUrl)..."

while ($Stopwatch.Elapsed.TotalSeconds -lt $MaxWaitSeconds) {
    Start-Sleep -Seconds $PollInterval
    try {
        $response = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec 3 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            $Ready = $true
            break
        }
    } catch {
        # Not ready yet
    }
    $elapsed = [math]::Round($Stopwatch.Elapsed.TotalSeconds)
    Write-Host "  waiting... (${elapsed}s)"
}

$Stopwatch.Stop()

if ($Ready) {
    $elapsed = [math]::Round($Stopwatch.Elapsed.TotalSeconds)
    Write-Host ""
    Write-Host "vLLM ready in ${elapsed}s at $Url"
} else {
    Write-Host ""
    Write-Host "vLLM did not become healthy within ${MaxWaitSeconds}s."
    Write-Host "Check the log:  wsl -e bash -c 'cat $VllmLog'"
    Write-Host "Check GPU:      wsl -e bash -c 'nvidia-smi'"
    exit 1
}
