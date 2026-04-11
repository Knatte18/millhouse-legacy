# spawn-agent.ps1 — Dispatch a prompt to the configured LLM backend.
# Reads llm-backend settings from _millhouse/config.yaml, health-checks the
# provider, and runs `claude --bare -p` pointed at the backend.
#
# Exit codes:
#   0 — success (result on stdout)
#   1 — hard failure (backend healthy but invocation failed — do NOT fallback)
#   2 — fallback (backend not configured or not healthy — use Agent tool)

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PromptFile,

    [int]$MaxTurns = 20,

    [string]$WorkDir = $PWD
)

$ErrorActionPreference = "Stop"

# --- Resolve config ---
$ConfigPath = Join-Path $WorkDir "_millhouse/config.yaml"
if (-not (Test-Path $ConfigPath)) {
    Write-Host "[spawn-agent] No config found at $ConfigPath — fallback"
    exit 2
}

$ConfigLines = Get-Content $ConfigPath -Encoding UTF8

# --- Check llm-backend.enabled ---
$Enabled = $false
$Provider = "vllm"
$FallbackToClaude = $true

$InBackendBlock = $false
$InVllmBlock = $false
$Url = "http://localhost:8000"
$ModelName = "default"

foreach ($line in $ConfigLines) {
    if ($line -match '^llm-backend:\s*$') {
        $InBackendBlock = $true
        $InVllmBlock = $false
        continue
    }
    if ($InBackendBlock -and $line -match '^\S' -and $line -notmatch '^llm-backend:') {
        $InBackendBlock = $false
        $InVllmBlock = $false
        continue
    }
    if ($InBackendBlock) {
        if ($line -match '^\s+enabled:\s*(.+)$') {
            $val = $Matches[1].Trim()
            $Enabled = ($val -eq 'true')
        }
        if ($line -match '^\s+provider:\s*(.+)$') { $Provider = $Matches[1].Trim() }
        if ($line -match '^\s+fallback-to-claude:\s*(.+)$') {
            $FallbackToClaude = ($Matches[1].Trim() -eq 'true')
        }
        if ($line -match '^\s+vllm:\s*$') {
            $InVllmBlock = $true
            continue
        }
        if ($InVllmBlock) {
            if ($line -match '^\s{4,}url:\s*(.+)$') { $Url = $Matches[1].Trim() }
            if ($line -match '^\s{4,}model-name:\s*(.+)$') { $ModelName = $Matches[1].Trim() }
            # Exit vllm block on less-indented line
            if ($line -match '^\s{1,3}\S') { $InVllmBlock = $false }
        }
    }
}

if (-not $Enabled) {
    Write-Host "[spawn-agent] llm-backend not enabled — fallback"
    exit 2
}

if ($Provider -ne "vllm") {
    Write-Host "[spawn-agent] Provider '$Provider' not supported — fallback"
    exit 2
}

# --- Health check ---
$HealthUrl = "$Url/health"
Write-Host "[spawn-agent] Health check: $HealthUrl"

try {
    $response = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
    if ($response.StatusCode -ne 200) {
        Write-Host "[spawn-agent] Health check returned $($response.StatusCode) — fallback"
        exit 2
    }
} catch {
    Write-Host "[spawn-agent] Backend not reachable at $HealthUrl — fallback"
    exit 2
}

Write-Host "[spawn-agent] Backend healthy. Using $Provider at $Url"

# --- Set environment variables ---
$env:ANTHROPIC_BASE_URL = $Url
$env:ANTHROPIC_API_KEY = "dummy"
$env:ANTHROPIC_DEFAULT_SONNET_MODEL = $ModelName
$env:ANTHROPIC_DEFAULT_OPUS_MODEL = $ModelName
$env:ANTHROPIC_DEFAULT_HAIKU_MODEL = $ModelName

# --- Set working directory ---
Set-Location $WorkDir

# --- Read prompt ---
if (-not (Test-Path $PromptFile)) {
    Write-Error "[spawn-agent] Prompt file not found: $PromptFile"
    exit 1
}

# --- Invoke claude --bare -p ---
# Pipe the prompt via stdin to avoid the Windows 32767-char command-line limit.
# claude --bare -p reads from stdin when no positional prompt argument is given.
Write-Host "[spawn-agent] Running claude --bare -p ... --model $ModelName --max-turns $MaxTurns"

try {
    $output = Get-Content $PromptFile -Raw -Encoding UTF8 |
        & claude --bare -p --model $ModelName --max-turns $MaxTurns --output-format json 2>&1
    $exitCode = $LASTEXITCODE
} catch {
    Write-Error "[spawn-agent] claude --bare threw exception: $_"
    exit 1
}

if ($exitCode -ne 0) {
    Write-Error "[spawn-agent] claude --bare exited with code $exitCode"
    exit 1
}

# --- Parse JSON output ---
try {
    $json = $output | Out-String | ConvertFrom-Json
    $result = $json.result
} catch {
    # If JSON parsing fails, treat the raw output as the result
    $result = $output | Out-String
}

if (-not $result) {
    Write-Error "[spawn-agent] Empty result from claude --bare"
    exit 1
}

# --- Output result ---
Write-Output $result
