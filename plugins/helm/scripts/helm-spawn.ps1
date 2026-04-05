# helm-spawn.ps1 — Create a worktree for a Helm task.
# Called by the helm-spawn skill. Delegates worktree creation to
# spawn-worktree.ps1, then adds Helm-specific structure: _helm/ dirs,
# board.kanban.md with task in Discussing, and opens VS Code.
#
# The skill handles: backlog reading, handoff brief, status.md.
# This script handles: worktree creation, _helm/ dirs, board, VS Code.
#
# Stdout contract: the ONLY Write-Output is $WorktreePath as the final line.
# The helm-spawn skill parses this to locate the new worktree.

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$TaskTitle,

    [string]$TaskBody = "",

    [Parameter(Mandatory)]
    [string]$ParentBranch,

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# --- Resolve repo root ---
$RepoRoot = (git rev-parse --show-toplevel 2>&1).Trim()
if ($LASTEXITCODE -ne 0) {
    Write-Error "Not in a git repository."
    exit 1
}
$RepoName = Split-Path $RepoRoot -Leaf

# --- Read config ---
$ConfigPath = Join-Path $RepoRoot "_helm" | Join-Path -ChildPath "config.yaml"
if (-not (Test-Path $ConfigPath)) {
    Write-Error "Config not found: $ConfigPath"
    exit 1
}

$ConfigContent = Get-Content $ConfigPath -Raw
$BranchTemplate = ""
$PathTemplate = ""
foreach ($line in ($ConfigContent -split "`n")) {
    $trimmed = $line.Trim()
    if ($trimmed -match '^branch-template:\s*"(.+)"$') {
        $BranchTemplate = $Matches[1]
    }
    if ($trimmed -match '^path-template:\s*"(.+)"$') {
        $PathTemplate = $Matches[1]
    }
}
if (-not $BranchTemplate -or -not $PathTemplate) {
    Write-Error "Could not parse branch-template or path-template from $ConfigPath"
    exit 1
}

# --- Generate slug ---
$Slug = $TaskTitle.ToLower() -replace '\s+', '-' -replace '[^a-z0-9\-]', ''
if ($Slug.Length -gt 20) { $Slug = $Slug.Substring(0, 20) }
$Slug = $Slug.TrimEnd('-')

# --- Resolve templates ---
$BranchName = $BranchTemplate -replace '\{slug\}', $Slug -replace '\{parent-branch\}', $ParentBranch -replace '\{repo-name\}', $RepoName
$RelativePath = $PathTemplate -replace '\{slug\}', $Slug -replace '\{parent-branch\}', $ParentBranch -replace '\{repo-name\}', $RepoName
$DirName = Split-Path $RelativePath -Leaf

# --- Call spawn-worktree.ps1 ---
$SpawnScript = Join-Path $RepoRoot "spawn-worktree.ps1"
if (-not (Test-Path $SpawnScript)) {
    Write-Error "spawn-worktree.ps1 not found at: $SpawnScript"
    exit 1
}

$spawnArgs = @{
    Branch = $BranchName
    DirName = $DirName
    NoOpen = $true
}
if ($DryRun) { $spawnArgs.DryRun = $true }

$output = & $SpawnScript @spawnArgs
$WorktreePath = ($output | Select-Object -Last 1).Trim()

if ($DryRun) {
    Write-Host ""
    Write-Host "[DryRun] Would create _helm/ directory structure."
    Write-Host "[DryRun] Would create board.kanban.md with 6 columns."
    Write-Host "[DryRun] Would open VS Code."
    Write-Output $WorktreePath
    exit 0
}

# --- Create _helm structure ---
New-Item -ItemType Directory -Path (Join-Path $WorktreePath "_helm/scratch/briefs") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $WorktreePath "_helm/scratch/plans") -Force | Out-Null

# --- Create board.kanban.md (6-column work board) ---
$kanbansDir = Join-Path $WorktreePath "kanbans"
New-Item -ItemType Directory -Path $kanbansDir -Force | Out-Null

$boardLines = @("# $RepoName", "", "## Discussing", "", "### $TaskTitle")
if ($TaskBody) {
    $indentedBody = ($TaskBody -split "`n" | ForEach-Object { "    $_" }) -join "`n"
    $boardLines += ""
    $boardLines += '    ```md'
    $boardLines += $indentedBody
    $boardLines += '    ```'
}
$boardLines += @("", "## Planned", "", "## Implementing", "", "## Testing", "", "## Reviewing", "", "## Blocked", "")
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $kanbansDir "board.kanban.md"), ($boardLines -join "`n"), $utf8NoBom)

# --- Open VS Code ---
Write-Host "Opening VS Code..."
$codeCmdPath = Get-Command "code.cmd" -ErrorAction SilentlyContinue
if ($codeCmdPath) {
    & code.cmd $WorktreePath | Out-Null
} else {
    Write-Warning "code.cmd not found on PATH. Open manually: $WorktreePath"
}

Write-Host "Worktree created at $WorktreePath on branch $BranchName"

# --- Stdout contract: bare worktree path as the only Write-Output ---
Write-Output $WorktreePath
