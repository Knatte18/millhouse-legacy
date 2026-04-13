# spawn-agent.ps1 — Unified subagent spawn script for mill.
#
# Dispatches a prompt file to a configured LLM backend and returns a
# role-validated JSON line on stdout. This is the single swap point for
# future backend additions; today the `claude` and `gemini` backends are wired.
#
# Parameters:
#   -Role          reviewer | implementer (required)
#   -PromptFile    path to materialized prompt file (required)
#   -ProviderName  model name (required); opus|sonnet|haiku → claude backend;
#                  gemini-3-pro|gemini-flash → gemini backend
#   -DispatchMode  tool-use | bulk (default: tool-use)
#   -BulkOutputFile path where bulk worker stdout is saved (required when
#                  -DispatchMode is bulk)
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
#   1  infrastructure error (backend failure, JSON parse error,
#      missing prompt file, validation failure, missing BulkOutputFile)
#   3  not-implemented backend (-ProviderName is not a recognized model
#      name, or dispatch mode not supported for the provider)
#  10  Gemini 429 / rate limit
#  11  Gemini OAuth bot-gate
#  12  Gemini binary not found
#  13  Gemini unclassified non-zero exit
#
# Synchronicity: this script is synchronous from its own perspective.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('reviewer', 'implementer')]
    [string]$Role,

    [Parameter(Mandatory = $true)]
    [string]$PromptFile,

    [Parameter(Mandatory = $true)]
    [string]$ProviderName,

    [ValidateSet('tool-use', 'bulk')]
    [string]$DispatchMode = 'tool-use',

    [string]$BulkOutputFile = '',

    [ValidateSet('', 'low', 'medium', 'high', 'max')]
    [string]$Effort = '',

    [int]$MaxTurns,

    [string]$WorkDir = $PWD
)

$ErrorActionPreference = "Stop"

# PS 7.3+ promotes any native-command stderr line or non-zero exit code
# into a terminating error when ErrorActionPreference=Stop. That turns
# Gemini CLI's transient 429 retry log into a fatal exception, killing
# the subprocess before Gemini's built-in retry can recover. Disable
# strict native-command error handling — we check $LASTEXITCODE ourselves.
$PSNativeCommandUseErrorActionPreference = $false

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

# --- Provider sets ---
$ClaudeModels = @('opus', 'sonnet', 'haiku')
$GeminiModels = @('gemini-3-pro', 'gemini-flash')


# --- Unknown provider ---
if ($ClaudeModels -notcontains $ProviderName -and $GeminiModels -notcontains $ProviderName) {
    Write-Log "Provider '$ProviderName' not implemented in this task. See plugins/mill/doc/overview.md#config-migration for follow-up."
    exit 3
}

# --- Working directory ---
Set-Location $WorkDir

Write-Log "Role=$Role Provider=$ProviderName DispatchMode=$DispatchMode MaxTurns=$MaxTurns PromptFile=$PromptFile"

# =============================================================================
# Claude backend
# =============================================================================
if ($ClaudeModels -contains $ProviderName) {

    # --- Claude bulk mode ---
    # Same shape as Gemini bulk: pipe materialized prompt via stdin, capture
    # text response, save to BulkOutputFile, parse VERDICT, emit JSON contract.
    # --max-turns 1 forbids tool calls so it's a true single-shot.
    if ($DispatchMode -eq 'bulk') {
        if ([string]::IsNullOrEmpty($BulkOutputFile)) {
            [Console]::Error.WriteLine("[spawn-agent] -BulkOutputFile is required when -DispatchMode is bulk")
            exit 1
        }

        try {
            $bulkClaudeArgs = @('-p', '--model', $ProviderName, '--max-turns', '1', '--output-format', 'json')
            if ($Effort -ne '') { $bulkClaudeArgs += @('--effort', $Effort) }
            Write-Log "claude bulk args: $($bulkClaudeArgs -join ' ')"
            $bulkRaw = Get-Content $PromptFile -Raw -Encoding UTF8 |
                & claude @bulkClaudeArgs 2>&1
            $bulkExit = $LASTEXITCODE
        } catch {
            Write-Log "claude bulk threw exception: $_"
            exit 1
        }

        if ($bulkExit -ne 0) {
            Write-Log "claude bulk exited with code $bulkExit. Output: $bulkRaw"
            exit 1
        }

        # claude -p --output-format json wraps result text in {"result": "..."}
        $bulkRawString = ($bulkRaw | Out-String).Trim()
        try {
            $bulkWrapper = $bulkRawString | ConvertFrom-Json -ErrorAction Stop
            $bulkResponse = $bulkWrapper.result
        } catch {
            Write-Log "Failed to parse claude bulk JSON wrapper. Output: $bulkRawString"
            exit 1
        }

        if ([string]::IsNullOrWhiteSpace($bulkResponse)) {
            Write-Log "Empty bulk response from claude. Wrapper: $bulkRawString"
            exit 1
        }

        $bulkAbsPath = [System.IO.Path]::GetFullPath($BulkOutputFile)
        [System.IO.File]::WriteAllText($bulkAbsPath, $bulkResponse, [System.Text.UTF8Encoding]::new($false))
        Write-Log "claude bulk worker output saved to $bulkAbsPath"

        # Parse VERDICT line from response
        $bulkLines = @($bulkResponse -split "`n" | ForEach-Object { $_.TrimEnd() })
        $parsedVerdict = $null
        for ($i = $bulkLines.Count - 1; $i -ge 0; $i--) {
            $line = $bulkLines[$i].Trim().TrimStart('*', '_', '#', '>', ' ').TrimEnd('*', '_', ' ')
            if ($line -match '^VERDICT:\s*(APPROVE|REQUEST_CHANGES|GAPS_FOUND)\s*$') {
                $parsedVerdict = $Matches[1]
                break
            }
        }

        if (-not $parsedVerdict) {
            $tail = ($bulkLines | Select-Object -Last 20) -join "`n"
            [Console]::Error.WriteLine("[spawn-agent] claude bulk worker did not emit VERDICT: line")
            [Console]::Error.WriteLine($tail)
            exit 1
        }

        $verdictObj = [ordered]@{ verdict = $parsedVerdict; review_file = $bulkAbsPath }
        Write-Output ($verdictObj | ConvertTo-Json -Compress)
        exit 0
    }

    # --- Invoke claude -p with prompt piped via stdin ---
    # Pipe via stdin to avoid Windows 32767-char command-line limit.
    # Capture stdout and stderr together (`2>&1`) so claude CLI errors are
    # visible if the result field ends up empty.
    #
    # NOTE: --bare was removed. It was a cargo-cult leftover from a previously-removed
    # Qwen/vLLM backend and it blocks OAuth credential resolution in the subprocess,
    # causing "Not logged in" errors.

    try {
        $claudeArgs = @('-p', '--model', $ProviderName, '--max-turns', $MaxTurns, '--output-format', 'json')
        if ($Effort -ne '') { $claudeArgs += @('--effort', $Effort) }
        Write-Log "claude args: $($claudeArgs -join ' ')"
        $rawOutput = Get-Content $PromptFile -Raw -Encoding UTF8 |
            & claude @claudeArgs 2>&1
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
    $resultText = $resultText.Trim()

    # Strip markdown inline-code backtick wrapping if the agent wrapped the JSON in backticks.
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
}

# =============================================================================
# Gemini backend
# =============================================================================

# Map millhouse provider name to Gemini-native model name
$geminiModel = switch ($ProviderName) {
    'gemini-3-pro'  { 'gemini-3-pro-preview' }
    'gemini-flash'  { 'gemini-3-flash-preview' }
}

# Resolve gemini binary. Precedence:
#   1. $env:MILLHOUSE_GEMINI_CLI (explicit override; set in shell profile or a per-machine .env)
#   2. `gemini` on PATH
$geminiBinary = $null
if ($env:MILLHOUSE_GEMINI_CLI -and (Test-Path $env:MILLHOUSE_GEMINI_CLI)) {
    $geminiBinary = $env:MILLHOUSE_GEMINI_CLI
} else {
    $onPath = Get-Command gemini -ErrorAction SilentlyContinue
    if ($onPath) { $geminiBinary = $onPath.Source }
}

if (-not $geminiBinary) {
    [Console]::Error.WriteLine("[spawn-agent] gemini binary not found. Set `$env:MILLHOUSE_GEMINI_CLI or add 'gemini' to PATH")
    exit 12
}

# --- Gemini bulk mode ---
if ($DispatchMode -eq 'bulk') {

    # Validate -BulkOutputFile is provided
    if ([string]::IsNullOrEmpty($BulkOutputFile)) {
        [Console]::Error.WriteLine("[spawn-agent] -BulkOutputFile is required when -DispatchMode is bulk")
        exit 1
    }

    $stderrTmpBulk = [System.IO.Path]::GetTempFileName()

    # Scope EAP=Continue around the subprocess call. With EAP=Stop, PS elevates
    # any native-command stderr line (including Gemini CLI's transient retry
    # log) into a terminating exception, killing the worker before the CLI's
    # built-in retry can recover. EAP=Continue lets the subprocess run to
    # completion; we check $LASTEXITCODE afterwards.
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        # Bulk mode: prompt piped via stdin, no -y, no -o json.
        # The gemini CLI with `-p -` reads the prompt from stdin.
        $bulkStdout = Get-Content $PromptFile -Raw -Encoding UTF8 |
            & $geminiBinary -p - --model $geminiModel 2> $stderrTmpBulk
        $bulkExitCode = $LASTEXITCODE
    } catch {
        Write-Log "gemini.cmd bulk threw exception: $_"
        if (Test-Path $stderrTmpBulk) { Remove-Item $stderrTmpBulk -Force }
        $ErrorActionPreference = $savedEAP
        exit 1
    } finally {
        $ErrorActionPreference = $savedEAP
    }

    $bulkStderrContent = ''
    if (Test-Path $stderrTmpBulk) {
        $bulkStderrContent = (Get-Content $stderrTmpBulk -Raw -Encoding UTF8 -ErrorAction SilentlyContinue)
        if ($bulkStderrContent) { $bulkStderrContent = $bulkStderrContent.Trim() }
        Remove-Item $stderrTmpBulk -Force
    }

    Write-Log "gemini bulk exit=$bulkExitCode stderr=$bulkStderrContent"

    $bulkStdoutString = ($bulkStdout | Out-String).Trim()

    if ($bulkExitCode -ne 0) {
        # Classify Gemini failures
        $combined = $bulkStdoutString + $bulkStderrContent
        if ($combined -match '429|RESOURCE_EXHAUSTED|rate limit') {
            [Console]::Error.WriteLine("[spawn-agent] gemini 429 rate limit")
            exit 10
        }
        if ($combined -match 'automated queries|cloudcode-pa\.googleapis\.com') {
            [Console]::Error.WriteLine("[spawn-agent] gemini oauth bot-gate")
            exit 11
        }
        $bulkStderrLines = @($bulkStderrContent -split "`n")
        $bulkTail = ($bulkStderrLines | Select-Object -Last 20) -join "`n"
        [Console]::Error.WriteLine("[spawn-agent] gemini exited non-zero")
        [Console]::Error.WriteLine($bulkTail)
        exit 13
    }

    # Save worker stdout to BulkOutputFile (UTF-8, no BOM)
    # [IO.File]::WriteAllText writes UTF-8 without BOM in .NET 4.x on Windows
    $bulkAbsPath = [System.IO.Path]::GetFullPath($BulkOutputFile)
    [System.IO.File]::WriteAllText($bulkAbsPath, $bulkStdoutString, [System.Text.UTF8Encoding]::new($false))

    Write-Log "bulk worker output saved to $bulkAbsPath"

    # Parse VERDICT: line from worker stdout (scan from bottom, case-sensitive VERDICT)
    $bulkLines = @($bulkStdoutString -split "`n" | ForEach-Object { $_.TrimEnd() })
    $parsedVerdict = $null
    for ($i = $bulkLines.Count - 1; $i -ge 0; $i--) {
        $line = $bulkLines[$i]
        if ($line -match '^VERDICT:\s*(APPROVE|REQUEST_CHANGES|GAPS_FOUND)\s*$') {
            $parsedVerdict = $Matches[1]
            break
        }
    }

    if (-not $parsedVerdict) {
        # Log last 20 lines for debuggability then fail
        $last20 = ($bulkLines | Select-Object -Last 20) -join "`n"
        [Console]::Error.WriteLine("[spawn-agent] bulk worker did not emit VERDICT: line")
        [Console]::Error.WriteLine($last20)
        exit 1
    }

    # Emit standard reviewer JSON contract on behalf of the worker.
    # Use ConvertTo-Json so backslash escaping is handled correctly.
    $verdictObj = [ordered]@{ verdict = $parsedVerdict; review_file = $bulkAbsPath }
    Write-Output ($verdictObj | ConvertTo-Json -Compress)
    exit 0
}

# --- Gemini tool-use mode ---
# Create a temp file for stderr to avoid mixing with stdout.
$stderrTmp = [System.IO.Path]::GetTempFileName()

try {
    $stdoutRaw = Get-Content $PromptFile -Raw -Encoding UTF8 |
        & $geminiBinary -y -o json --model $geminiModel 2> $stderrTmp
    $exitCode = $LASTEXITCODE
} catch {
    Write-Log "gemini.cmd threw exception: $_"
    if (Test-Path $stderrTmp) { Remove-Item $stderrTmp -Force }
    exit 1
}

# Read and log stderr (contains NODE_TLS_REJECT_UNAUTHORIZED=0 warning; harmless)
$stderrContent = ''
if (Test-Path $stderrTmp) {
    $stderrContent = (Get-Content $stderrTmp -Raw -Encoding UTF8 -ErrorAction SilentlyContinue)
    if ($stderrContent) { $stderrContent = $stderrContent.Trim() }
    Remove-Item $stderrTmp -Force
}

Write-Log "gemini exit=$exitCode stderr=$stderrContent"

if ($exitCode -ne 0) {
    # Classify Gemini failures
    $combined = ($stdoutRaw | Out-String) + $stderrContent
    if ($combined -match '429|RESOURCE_EXHAUSTED|rate limit' ) {
        [Console]::Error.WriteLine("[spawn-agent] gemini 429 rate limit")
        exit 10
    }
    if ($combined -match 'automated queries|cloudcode-pa\.googleapis\.com') {
        [Console]::Error.WriteLine("[spawn-agent] gemini oauth bot-gate")
        exit 11
    }
    # Unclassified — print last 20 lines of stderr for debuggability
    $stderrLines = @($stderrContent -split "`n")
    $tail = ($stderrLines | Select-Object -Last 20) -join "`n"
    [Console]::Error.WriteLine("[spawn-agent] gemini exited non-zero")
    [Console]::Error.WriteLine($tail)
    exit 13
}

# --- Parse Gemini's JSON wrapper ---
# Gemini -o json outputs: {"response": "<text>", ...}
# Fall back to raw stdout if JSON parse fails.
$stdoutString = ($stdoutRaw | Out-String).Trim()

$resultText = $null
try {
    $gemWrapper = $stdoutString | ConvertFrom-Json -ErrorAction Stop
    if ($gemWrapper.PSObject.Properties['response']) {
        $resultText = $gemWrapper.response
    }
} catch {
    # JSON parse failed — use raw stdout as result text
}

if ([string]::IsNullOrWhiteSpace($resultText)) {
    $resultText = $stdoutString
}

$resultText = $resultText.Trim()

# Strip markdown backtick wrapping
if ($resultText.StartsWith('`') -and $resultText.EndsWith('`')) {
    $resultText = $resultText.Substring(1, $resultText.Length - 2).Trim()
}

# Extract the JSON line (scan from bottom)
$jsonLine = $null
$obj = $null
try {
    $obj = $resultText | ConvertFrom-Json -ErrorAction Stop
    $jsonLine = $resultText
} catch {
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
    Write-Log "Could not find a JSON line in Gemini result. Result: $resultText"
    exit 1
}

# --- Role-specific validation (same as Claude path) ---
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

Write-Output $jsonLine
exit 0
