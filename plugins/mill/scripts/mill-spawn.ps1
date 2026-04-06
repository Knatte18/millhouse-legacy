# mill-spawn.ps1 — Self-contained worktree spawner for Mill tasks.
# Reads backlog, claims the first task from Spawn, creates the worktree,
# writes handoff brief / status / board, commits backlog change, opens VS Code.
#
# No Claude session needed — all logic is deterministic text processing.
#
# Stdout contract: the ONLY Write-Output is $ProjectPath as the final line.

[CmdletBinding()]
param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# --- Resolve repo root (needed for git operations) ---
$RepoRoot = (git rev-parse --show-toplevel 2>&1).Trim()
if ($LASTEXITCODE -ne 0) {
    Write-Error "Not in a git repository."
    exit 1
}

# --- Config guard (cwd-relative) ---
$ConfigPath = Join-Path $PWD "_millhouse/config.yaml"
if (-not (Test-Path $ConfigPath)) {
    Write-Error "mill-setup has not been run. Please run mill-setup first."
    exit 1
}

# --- Read backlog (cwd-relative) ---
$BacklogPath = Join-Path $PWD "_millhouse/backlog.kanban.md"
if (-not (Test-Path $BacklogPath)) {
    Write-Error "_millhouse/backlog.kanban.md not found. Run mill-setup first."
    exit 1
}

$BacklogContent = Get-Content $BacklogPath -Raw -Encoding UTF8

# --- Parse project title (first # heading) ---
if ($BacklogContent -match '(?m)^# (.+)$') {
    $ProjectTitle = $Matches[1].Trim()
} else {
    $ProjectTitle = "Project"
}

# --- Find first task in ## Spawn column ---
# Strategy: find the ## Spawn section, then find the first ### heading within it.
# The Spawn section ends at the next ## heading or end of file.

$spawnMatch = [regex]::Match($BacklogContent, '(?m)^## Spawn\s*\r?\n')
if (-not $spawnMatch.Success) {
    Write-Error "No ## Spawn column found in backlog."
    exit 1
}

$spawnStart = $spawnMatch.Index + $spawnMatch.Length

# Find next ## heading after Spawn (= end of Spawn section)
$h2Regex = [regex]::new('(?m)^## ')
$nextColumnMatch = $h2Regex.Match($BacklogContent, $spawnStart)
if ($nextColumnMatch.Success) {
    $spawnEnd = $nextColumnMatch.Index
} else {
    $spawnEnd = $BacklogContent.Length
}

$spawnSection = $BacklogContent.Substring($spawnStart, $spawnEnd - $spawnStart)

# Find first ### heading in Spawn section
$taskMatch = [regex]::Match($spawnSection, '(?m)^### (.+)$')
if (-not $taskMatch.Success) {
    Write-Host "No tasks in Spawn column."
    exit 0
}

$TaskTitle = $taskMatch.Groups[1].Value.Trim()
# Strip [phase] suffix if present
$TaskTitle = $TaskTitle -replace '\s*\[.*?\]\s*$', ''

# Capture full task block: from ### heading to next ### or end of Spawn section
$taskBlockStart = $taskMatch.Index
$h3Regex = [regex]::new('(?m)^### ')
$nextTaskMatch = $h3Regex.Match($spawnSection, $taskBlockStart + $taskMatch.Length)
if ($nextTaskMatch.Success) {
    $taskBlockEnd = $nextTaskMatch.Index
} else {
    $taskBlockEnd = $spawnSection.Length
}

$TaskBlock = $spawnSection.Substring($taskBlockStart, $taskBlockEnd - $taskBlockStart)

# Extract description from task block (indented ```md ... ``` block)
$TaskDescription = ""
if ($TaskBlock -match '(?s)```md\s*\r?\n(.+?)```') {
    $TaskDescription = $Matches[1].Trim()
}

# --- Remove task block from backlog (in-memory) ---
$updatedSpawnSection = $spawnSection.Remove($taskBlockStart, $taskBlockEnd - $taskBlockStart)
$UpdatedBacklog = $BacklogContent.Substring(0, $spawnStart) + $updatedSpawnSection + $BacklogContent.Substring($spawnEnd)

# --- Generate slug ---
$Slug = $TaskTitle.ToLower() -replace '\s+', '-' -replace '[^a-z0-9\-]', ''
if ($Slug.Length -gt 20) { $Slug = $Slug.Substring(0, 20) }
$Slug = $Slug.TrimEnd('-')

# --- Read branch-prefix from config ---
$BranchPrefix = ""
foreach ($cfgLine in (Get-Content $ConfigPath -Encoding UTF8)) {
    if ($cfgLine -match '^\s*branch-prefix:\s*(.+)$') {
        $val = $Matches[1].Trim()
        if ($val -ne '~' -and $val -ne 'null' -and $val -ne '""' -and $val -ne "''") {
            $BranchPrefix = $val.Trim('"', "'")
        }
    }
}

if ($BranchPrefix) {
    $BranchName = "$BranchPrefix/$Slug"
} else {
    $BranchName = $Slug
}

Write-Host "Task:      $TaskTitle"
Write-Host "Branch:    $BranchName"

if ($DryRun) {
    Write-Host ""
    Write-Host "[DryRun] Would write handoff to _millhouse/handoff.md"
    Write-Host "[DryRun] Would remove task '$TaskTitle' from Spawn column."
    Write-Host "[DryRun] Would commit backlog + handoff.md (spawn: $TaskTitle)"
    Write-Host "[DryRun] Would create worktree via mill-worktree.ps1 (branch: $BranchName)"
    Write-Host "[DryRun] Would write status.md and board.kanban.md in new worktree"
    exit 0
    # Note: DryRun exits without emitting Write-Output $ProjectPath.
}

# --- Validate updated backlog BEFORE writing to disk ---
# Validation must run first so a format failure never leaves the board corrupted.
$backlogLines = $UpdatedBacklog -split '\r?\n'
$h1Count = 0
$h2Headings = @()
$h3BeforeH2 = $false
$firstH2Index = -1
$strayContent = $false

for ($i = 0; $i -lt $backlogLines.Count; $i++) {
    $line = $backlogLines[$i]
    if ($line -match '^# (?!#)') {
        $h1Count++
        if ($i -ne 0) {
            Write-Error "Validation failed: # heading is not on line 1."
            exit 1
        }
    }
    if ($line -match '^## (?!#)') {
        $h2Headings += $line.Trim()
        if ($firstH2Index -eq -1) { $firstH2Index = $i }
    }
    if ($line -match '^### ' -and $firstH2Index -eq -1) {
        $h3BeforeH2 = $true
    }
    if ($firstH2Index -eq -1 -and $i -gt 0 -and $line.Trim() -ne '' -and $line -notmatch '^#') {
        $strayContent = $true
    }
}

if ($h1Count -ne 1) {
    Write-Error "Validation failed: Expected exactly 1 # heading, found $h1Count."
    exit 1
}
$expectedH2 = @('## Backlog', '## Spawn', '## Delete')
if ($h2Headings.Count -ne 3) {
    Write-Error "Validation failed: Expected 3 ## headings, found $($h2Headings.Count)."
    exit 1
}
for ($i = 0; $i -lt 3; $i++) {
    if ($h2Headings[$i] -ne $expectedH2[$i]) {
        Write-Error "Validation failed: Expected '$($expectedH2[$i])' but found '$($h2Headings[$i])'."
        exit 1
    }
}
if ($h3BeforeH2) {
    Write-Error "Validation failed: ### heading found before first ## heading."
    exit 1
}
if ($strayContent) {
    Write-Error "Validation failed: Non-blank content between # heading and first ## heading."
    exit 1
}

# --- Read parent branch and config values (needed for handoff, before worktree creation) ---
$ParentBranch = (git branch --show-current 2>&1).Trim()

$VerifyCmd = "N/A"
$DevServerCmd = "N/A"
foreach ($line in (Get-Content $ConfigPath -Encoding UTF8)) {
    if ($line -match '^\s*verify:\s*(.+)$') { $VerifyCmd = $Matches[1].Trim() }
    if ($line -match '^\s*dev-server:\s*(.+)$') { $DevServerCmd = $Matches[1].Trim() }
}

# Normalize multi-line descriptions so every line carries 4-space indent inside the board code fence.
$rawSummary = if ($TaskDescription) { $TaskDescription } else { $TaskTitle }
$DiscussionSummary = ($rawSummary -split '\r?\n') -join "`n    "

# --- Write handoff to parent _millhouse/handoff.md (git-tracked) ---
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$handoffContent = @"
# Handoff: $TaskTitle

## Issue
$TaskTitle

## Parent
Branch: $ParentBranch
Worktree: $PWD

## Discussion Summary
$DiscussionSummary

## Config
- Verify: $VerifyCmd
- Dev server: $DevServerCmd
"@

$handoffPath = Join-Path $PWD "_millhouse" | Join-Path -ChildPath "handoff.md"
[System.IO.File]::WriteAllText($handoffPath, $handoffContent, $utf8NoBom)

# --- Write updated backlog and commit both backlog + handoff ---
[System.IO.File]::WriteAllText($BacklogPath, $UpdatedBacklog, $utf8NoBom)
$BacklogRelPath = $BacklogPath.Substring($RepoRoot.Length).TrimStart('\', '/')
$HandoffRelPath = $handoffPath.Substring($RepoRoot.Length).TrimStart('\', '/')
git -C $RepoRoot add $BacklogRelPath $HandoffRelPath
if ($LASTEXITCODE -ne 0) { Write-Error "git add failed."; exit 1 }
git -C $RepoRoot diff --cached --quiet 2>&1 | Out-Null; $hasChanges = ($LASTEXITCODE -ne 0)
if ($hasChanges) {
    git -C $RepoRoot commit -m "spawn: $TaskTitle"
    if ($LASTEXITCODE -ne 0) { Write-Error "git commit failed."; exit 1 }
    git -C $RepoRoot push
    if ($LASTEXITCODE -ne 0) { Write-Error "git push failed."; exit 1 }
}

# --- Locate mill-worktree.ps1 (three-tier resolution) ---
$WorktreeScript = $null

# Tier 1: plugin source (works in millhouse repo)
$tier1 = Join-Path $RepoRoot "plugins\mill\scripts\mill-worktree.ps1"
if (Test-Path $tier1) {
    $WorktreeScript = $tier1
}

# Tier 2: plugin cache (works in any repo with mill plugin installed)
if (-not $WorktreeScript) {
    $PluginBase = Join-Path $env:USERPROFILE ".claude\plugins\cache\millhouse\mill"
    if (Test-Path $PluginBase) {
        $VersionDir = Get-ChildItem $PluginBase -Directory |
            Where-Object { $_.Name -match '^\d+\.\d+\.\d+$' } |
            Sort-Object Name -Descending |
            Select-Object -First 1
        if ($VersionDir) {
            $tier2 = Join-Path $VersionDir.FullName "scripts\mill-worktree.ps1"
            if (Test-Path $tier2) { $WorktreeScript = $tier2 }
        }
    }
}

# Tier 3: sibling script in same plugin directory
if (-not $WorktreeScript) {
    $tier3 = Join-Path (Split-Path $MyInvocation.MyCommand.Path) "mill-worktree.ps1"
    if (Test-Path $tier3) { $WorktreeScript = $tier3 }
}

if (-not $WorktreeScript) {
    Write-Error "mill-worktree.ps1 not found. Install the mill plugin (claude plugin install mill@millhouse) or place a wrapper in the project directory."
    exit 1
}

# --- Create worktree (after commit — new worktree inherits handoff via git) ---
$spawnArgs = @{
    Branch   = $BranchName
    TaskName = $TaskTitle
    NoOpen   = $true
}

$output = & $WorktreeScript @spawnArgs
$ProjectPath = ($output | Select-Object -Last 1).Trim()
if (-not $ProjectPath -or -not (Test-Path $ProjectPath)) {
    Write-Error "mill-worktree.ps1 did not return a valid project path. Got: '$ProjectPath'"
    exit 1
}

# --- Create _millhouse/scratch structure in new worktree ---
New-Item -ItemType Directory -Path (Join-Path $ProjectPath "_millhouse/scratch/plans") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $ProjectPath "_millhouse/scratch/reviews") -Force | Out-Null

# --- Write status.md in new worktree ---
$statusContent = @"
parent: $ParentBranch
task: $TaskTitle
phase: discussing
"@

$statusPath = Join-Path $ProjectPath "_millhouse" | Join-Path -ChildPath "scratch"
$statusPath = Join-Path $statusPath "status.md"
[System.IO.File]::WriteAllText($statusPath, $statusContent, $utf8NoBom)

# --- Write board.kanban.md in new worktree ---
$boardContent = @"
# $ProjectTitle

## Discussing

### $TaskTitle

    ``````md
    $DiscussionSummary
    ``````

## Planned

## Implementing

## Testing

## Reviewing

## Blocked

"@

$boardPath = Join-Path $ProjectPath "_millhouse" | Join-Path -ChildPath "scratch"
$boardPath = Join-Path $boardPath "board.kanban.md"
$boardDir = Split-Path $boardPath -Parent
New-Item -ItemType Directory -Path $boardDir -Force | Out-Null
[System.IO.File]::WriteAllText($boardPath, $boardContent, $utf8NoBom)

# --- Open VS Code ---
Write-Host "Opening VS Code..."
$codeCmdPath = Get-Command "code.cmd" -ErrorAction SilentlyContinue
if ($codeCmdPath) {
    & code.cmd $ProjectPath | Out-Null
} else {
    Write-Warning "code.cmd not found on PATH. Open manually: $ProjectPath"
}

Write-Host ""
Write-Host "Worktree created at $ProjectPath on branch $BranchName"
Write-Host "Task: $TaskTitle"
Write-Host "Run mill-start in the new VS Code window to continue planning."

# --- Stdout contract: bare project path as the only Write-Output ---
Write-Output $ProjectPath
