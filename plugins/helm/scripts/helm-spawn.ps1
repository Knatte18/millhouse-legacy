# helm-spawn.ps1 — Create a worktree for a Helm task.
# Called by helm-start when the user chooses worktree mode.
# Delegates worktree creation to spawn-worktree.ps1, then adds
# Helm-specific files: _helm/ structure, kanban board, status.md,
# handoff brief copy.

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

# --- Generate slug and names ---
$Slug = $TaskTitle.ToLower() -replace '\s+', '-' -replace '[^a-z0-9\-]', ''
if ($Slug.Length -gt 20) { $Slug = $Slug.Substring(0, 20) }
$Slug = $Slug.TrimEnd('-')

$BranchName = "$ParentBranch-wt-$Slug"
$DirName = $Slug

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
    $briefSource = Join-Path $RepoRoot "_helm" | Join-Path -ChildPath "scratch" | Join-Path -ChildPath "briefs" | Join-Path -ChildPath "handoff.md"
    if (Test-Path $briefSource) {
        Write-Host "[DryRun] Would copy handoff brief from parent."
    } else {
        Write-Host "[DryRun] No handoff brief in parent - skipping."
    }
    Write-Host '[DryRun] Would write: kanbans/board.kanban.md, _helm/scratch/status.md'
    Write-Host "[DryRun] Would open VS Code."
    exit 0
}

# --- Create _helm structure ---
New-Item -ItemType Directory -Path (Join-Path $WorktreePath "_helm/scratch/briefs") -Force | Out-Null

# --- Kanban board file ---
$kanbansDir = Join-Path $WorktreePath "kanbans"
New-Item -ItemType Directory -Path $kanbansDir -Force | Out-Null

$boardLines = @("# $RepoName", "", "## Backlog", "", "## Spawn", "", "## In Progress", "", "### $TaskTitle [discussing]")
if ($TaskBody) {
    $indentedBody = ($TaskBody -split "`n" | ForEach-Object { "    $_" }) -join "`n"
    $boardLines += ""
    $boardLines += '    ```md'
    $boardLines += $indentedBody
    $boardLines += '    ```'
}
$boardLines += @("", "", "## Done", "", "## Blocked", "")
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $kanbansDir "board.kanban.md"), ($boardLines -join "`n"), $utf8NoBom)

# --- status.md ---
$statusContent = "task: $TaskTitle`nphase: discussing"
Set-Content -Path (Join-Path $WorktreePath "_helm/scratch/status.md") -Value $statusContent -Encoding UTF8

# --- Copy handoff brief (conditional) ---
$briefSource = Join-Path $RepoRoot "_helm/scratch/briefs/handoff.md"
$briefDest = Join-Path $WorktreePath "_helm/scratch/briefs/handoff.md"
if (Test-Path $briefSource) {
    Copy-Item $briefSource $briefDest
    Write-Host "Handoff brief copied."
}

# --- Open VS Code ---
Write-Host "Opening VS Code..."
$codeCmdPath = Get-Command "code.cmd" -ErrorAction SilentlyContinue
if ($codeCmdPath) {
    & code.cmd $WorktreePath
} else {
    $fallback = "C:\Users\henri\AppData\Local\Programs\Microsoft VS Code\bin\code.cmd"
    if (Test-Path $fallback) {
        & $fallback $WorktreePath
    } else {
        Write-Warning "code.cmd not found. Open manually: $WorktreePath"
    }
}

Write-Host ""
Write-Host "Worktree created at $WorktreePath on branch $BranchName"
