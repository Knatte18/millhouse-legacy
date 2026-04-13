# stub-spawn-agent.ps1 — Stub implementation of spawn-agent.ps1 for integration tests.
#
# Mimics the real spawn-agent.ps1 contract without calling any LLM.
# Used by test_spawn_reviewer_integration.py via SPAWN_AGENT_PATH env var.

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

    [int]$MaxTurns = 20,

    [string]$WorkDir = $PWD
)

$ErrorActionPreference = "Stop"

# Magic provider names that trigger specific failure modes
if ($ProviderName -eq 'stub-fail-429') {
    [Console]::Error.WriteLine("[stub-spawn-agent] gemini 429 rate limit")
    exit 10
}
if ($ProviderName -eq 'stub-fail-botgate') {
    [Console]::Error.WriteLine("[stub-spawn-agent] gemini oauth bot-gate")
    exit 11
}

# Stub review content
$stubContent = "## Summary`nstub ok`n`n## Blocking Findings`n(none)`n`nVERDICT: APPROVE`n"

if ($DispatchMode -eq 'bulk') {
    # Bulk mode: write stub content to BulkOutputFile and emit JSON
    if ([string]::IsNullOrEmpty($BulkOutputFile)) {
        [Console]::Error.WriteLine("[stub-spawn-agent] -BulkOutputFile is required when -DispatchMode is bulk")
        exit 1
    }
    $absPath = [System.IO.Path]::GetFullPath($BulkOutputFile)
    [System.IO.File]::WriteAllText($absPath, $stubContent, [System.Text.UTF8Encoding]::new($false))
    $jsonEscapedPath = $absPath -replace '\\', '\\\\'
    Write-Output ('{"verdict":"APPROVE","review_file":"' + $jsonEscapedPath + '"}')
    exit 0
}

# Tool-use mode: write stub review to a temp file and emit JSON
$stubReviewPath = [System.IO.Path]::GetTempFileName() -replace '\.tmp$', '.md'
[System.IO.File]::WriteAllText($stubReviewPath, $stubContent, [System.Text.UTF8Encoding]::new($false))
$jsonEscapedPath = $stubReviewPath -replace '\\', '\\\\'
Write-Output ('{"verdict":"APPROVE","review_file":"' + $jsonEscapedPath + '"}')
exit 0
