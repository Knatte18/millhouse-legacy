# spawn-agent.ps1 — Unified subagent spawn script for mill.
#
# Dispatches a prompt file to a configured LLM backend and returns a
# role-validated JSON line on stdout. This is the single swap point for
# future backend additions; today only the `claude` backend is wired.
#
# Parameters:
#   -Role          reviewer | implementer (required)
#   -PromptFile    path to materialized prompt file (required)
#   -ProviderName  model name (required); opus|sonnet|haiku → claude backend
#   -MaxTurns      optional override; defaults: reviewer=20, implementer=200
#   -WorkDir       optional working directory; defaults to $PWD
#
# Stdout contract: a single JSON line, role-dependent:
#   reviewer    → {"verdict": "...", "review_file": "..."}
#   implementer → {"phase": "...", "status_file": "...", "final_commit": "..."}
#
# All informational logging goes to stderr. Stdout is reserved for the
# final JSON line so callers can parse it cleanly.
#
# Exit codes:
#   0  success, JSON line on stdout
#   1  infrastructure error (claude backend failure, JSON parse error,
#      missing prompt file, validation failure)
#   3  not-implemented backend (-ProviderName is not a recognized Claude
#      model name in this task)
#
# Synchronicity: this script is synchronous from its own perspective.
# It pipes the prompt to `claude -p` via stdin and waits. Callers
# that need backgrounding (e.g. Thread B implementer runs) wrap the
# invocation in the Bash tool's `run_in_background: true` and use Monitor.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('reviewer', 'implementer')]
    [string]$Role,

    [Parameter(Mandatory = $true)]
    [string]$PromptFile,

    [Parameter(Mandatory = $true)]
    [string]$ProviderName,

    [int]$MaxTurns,

    [string]$WorkDir = $PWD
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message)
    [Console]::Error.WriteLine("[spawn-agent] $Message")
}

# --- Default MaxTurns by role ---
if (-not $PSBoundParameters.ContainsKey('MaxTurns') -or $MaxTurns -le 0) {
    if ($Role -eq 'reviewer') { $MaxTurns = 20 }
    else { $MaxTurns = 200 }
}

# --- Validate prompt file exists ---
if (-not (Test-Path $PromptFile)) {
    Write-Log "Prompt file not found: $PromptFile"
    exit 1
}

# --- Backend dispatch ---
$ClaudeModels = @('opus', 'sonnet', 'haiku')

if ($ClaudeModels -notcontains $ProviderName) {
    Write-Log "Provider '$ProviderName' not implemented in this task. See plugins/mill/doc/overview.md#config-migration for follow-up."
    exit 3
}

# --- Working directory ---
Set-Location $WorkDir

Write-Log "Role=$Role Provider=$ProviderName MaxTurns=$MaxTurns PromptFile=$PromptFile"

# --- Invoke claude -p with prompt piped via stdin ---
# Pipe via stdin to avoid Windows 32767-char command-line limit.
# Capture stdout and stderr together (`2>&1`) so claude CLI errors are
# visible if the result field ends up empty.
#
# NOTE: --bare was removed. It was a cargo-cult leftover from a previously-removed
# Qwen/vLLM backend and it blocks OAuth credential resolution in the subprocess,
# causing "Not logged in" errors. Trade-off: slightly slower startup and hooks
# run per spawn. Worth it — the script actually works now.

try {
    $rawOutput = Get-Content $PromptFile -Raw -Encoding UTF8 |
        & claude -p --model $ProviderName --max-turns $MaxTurns --output-format json 2>&1
    $exitCode = $LASTEXITCODE
} catch {
    Write-Log "claude -p threw exception: $_"
    exit 1
}

if ($exitCode -ne 0) {
    Write-Log "claude -p exited with code $exitCode. Output: $rawOutput"
    exit 1
}

# --- Parse JSON wrapper from claude -p ---
$rawOutputString = ($rawOutput | Out-String).Trim()

try {
    $wrapper = $rawOutputString | ConvertFrom-Json -ErrorAction Stop
} catch {
    Write-Log "Failed to parse claude -p JSON wrapper. Output: $rawOutputString"
    exit 1
}

$resultText = $wrapper.result
if ([string]::IsNullOrWhiteSpace($resultText)) {
    Write-Log "Empty or unparseable result from claude -p. Wrapper: $rawOutputString"
    exit 1
}

# --- Extract the JSON line from the result ---
# The agent's last line should be a JSON object. Trim and find the last
# {...} block in case the agent included preamble despite instructions.
$resultText = $resultText.Trim()

# Strip markdown inline-code backtick wrapping if the agent wrapped the JSON in backticks.
# Agents sometimes emit: `{"verdict": "APPROVE", ...}` instead of the bare JSON object.
if ($resultText.StartsWith('`') -and $resultText.EndsWith('`')) {
    $resultText = $resultText.Substring(1, $resultText.Length - 2).Trim()
}

# Try to parse the entire result as JSON first.
$jsonLine = $null
try {
    $obj = $resultText | ConvertFrom-Json -ErrorAction Stop
    $jsonLine = $resultText
} catch {
    # Fall back: scan for the last line that parses as JSON.
    # @() forces an array even when there is only one line — prevents PS5 scalar
    # unboxing where $lines[$i] would index into the string character-by-character.
    $lines = @($resultText -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
    for ($i = $lines.Count - 1; $i -ge 0; $i--) {
        $candidate = $lines[$i]
        if ($candidate.StartsWith('{') -and $candidate.EndsWith('}')) {
            try {
                $obj = $candidate | ConvertFrom-Json -ErrorAction Stop
                $jsonLine = $candidate
                break
            } catch {
                continue
            }
        }
    }
}

if (-not $jsonLine) {
    Write-Log "Could not find a JSON line in agent result. Result: $resultText"
    exit 1
}

# --- Role-specific validation ---
if ($Role -eq 'reviewer') {
    if (-not $obj.PSObject.Properties['verdict']) {
        Write-Log "Reviewer JSON missing 'verdict' field. Got: $jsonLine"
        exit 1
    }
    if (-not $obj.PSObject.Properties['review_file']) {
        Write-Log "Reviewer JSON missing 'review_file' field. Got: $jsonLine"
        exit 1
    }
} else {
    # implementer
    if (-not $obj.PSObject.Properties['phase']) {
        Write-Log "Implementer JSON missing 'phase' field. Got: $jsonLine"
        exit 1
    }
    if (-not $obj.PSObject.Properties['status_file']) {
        Write-Log "Implementer JSON missing 'status_file' field. Got: $jsonLine"
        exit 1
    }
    if (-not $obj.PSObject.Properties['final_commit']) {
        Write-Log "Implementer JSON missing 'final_commit' field. Got: $jsonLine"
        exit 1
    }
}

# --- Emit the JSON line on stdout ---
Write-Output $jsonLine
exit 0
