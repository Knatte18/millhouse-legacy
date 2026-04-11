# stop-qwen.ps1 — Stop vLLM in WSL.
# Kills any running vLLM serve process and verifies shutdown.

$ErrorActionPreference = "Stop"

Write-Host "Stopping vLLM..."
wsl -e bash -c "pkill -f 'vllm serve'" 2>$null

# --- Verify shutdown ---
Start-Sleep -Seconds 2

# Try to read config for the URL, fall back to default
$ConfigPath = Join-Path $PWD "_millhouse/config.yaml"
$HealthUrl = "http://localhost:8000/health"

if (Test-Path $ConfigPath) {
    $InVllmBlock = $false
    foreach ($line in (Get-Content $ConfigPath -Encoding UTF8)) {
        if ($line -match '^\s*vllm:\s*$') { $InVllmBlock = $true; continue }
        if ($InVllmBlock -and $line -match '^\S') { $InVllmBlock = $false }
        if ($InVllmBlock -and $line -match '^\s+url:\s*(http.+)$') {
            $HealthUrl = "$($Matches[1].Trim())/health"
            break
        }
    }
}

try {
    $null = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    Write-Warning "vLLM health endpoint still responding at $HealthUrl. Process may not have stopped."
} catch {
    Write-Host "vLLM stopped."
}
