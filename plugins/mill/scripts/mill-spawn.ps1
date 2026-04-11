# mill-spawn.ps1 — Self-contained worktree spawner for Mill tasks.
# Reads tasks.md, claims the first [>] task (changes to [discussing]),
# creates the worktree, writes handoff brief / status, commits tasks.md change.
#
# No Claude session needed — all logic is deterministic text processing.
#
# Stdout contract: the ONLY Write-Output is $ProjectPath as the final line.

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$VSCode
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

# --- Read tasks.md (project root) ---
$TasksPath = Join-Path $PWD "tasks.md"
if (-not (Test-Path $TasksPath)) {
    Write-Error "tasks.md not found in project root ($PWD). Run mill-setup first."
    exit 1
}

$TasksContent = Get-Content $TasksPath -Raw -Encoding UTF8

# --- Find first ## [>] task ---
$spawnMatch = [regex]::Match($TasksContent, '(?m)^## \[>\] (.+)$')
if (-not $spawnMatch.Success) {
    Write-Host "No [>] tasks in tasks.md."
    exit 0
}

$TaskTitle = $spawnMatch.Groups[1].Value.Trim()

# Capture full task block: from ## [>] heading to next ## or EOF
$taskBlockStart = $spawnMatch.Index
$h2Regex = [regex]::new('(?m)^## ')
$nextH2Match = $h2Regex.Match($TasksContent, $taskBlockStart + $spawnMatch.Length)
if ($nextH2Match.Success) {
    $taskBlockEnd = $nextH2Match.Index
} else {
    $taskBlockEnd = $TasksContent.Length
}

$TaskBlock = $TasksContent.Substring($taskBlockStart, $taskBlockEnd - $taskBlockStart)

# Extract description from bullet points
$TaskDescription = ""
$descLines = @()
foreach ($line in ($TaskBlock -split '\r?\n')) {
    if ($line -match '^\s*- (.+)$' -and $line -notmatch '^\s*- tags:') {
        $descLines += $Matches[1].Trim()
    }
}
if ($descLines.Count -gt 0) {
    $TaskDescription = $descLines -join "`n"
}

# --- Change [>] to [discussing] in tasks.md (in-memory) ---
$UpdatedTasks = $TasksContent.Substring(0, $spawnMatch.Index) + "## [discussing] $TaskTitle" + $TasksContent.Substring($spawnMatch.Index + $spawnMatch.Length)

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
    Write-Host "[DryRun] Would change [>] to [discussing] for task '$TaskTitle' in tasks.md."
    Write-Host "[DryRun] Would create worktree via mill-worktree.ps1 (branch: $BranchName)"
    Write-Host "[DryRun] Would copy _millhouse/ (excluding scratch/) to new worktree"
    Write-Host "[DryRun] Would write status.md in new worktree"
    exit 0
    # Note: DryRun exits without emitting Write-Output $ProjectPath.
}

# --- Validate updated tasks.md BEFORE writing to disk ---
$tasksLines = $UpdatedTasks -split '\r?\n'
$h1Count = 0
$h2Headings = @()
$validPhases = @('discussing', 'discussed', 'planned', 'implementing', 'testing', 'reviewing', 'blocked', 'pr-pending', 'done', '>')

for ($i = 0; $i -lt $tasksLines.Count; $i++) {
    $line = $tasksLines[$i]
    if ($line -match '^# (?!#)') {
        $h1Count++
        if ($i -ne 0) {
            Write-Error "Validation failed: # heading is not on line 1."
            exit 1
        }
    }
    if ($line -match '^## (?!#)') {
        $h2Headings += $line.Trim()
        # Check phase marker if present
        if ($line -match '^## \[([>\w]+)\]') {
            $phase = $Matches[1]
            if ($validPhases -notcontains $phase) {
                Write-Error "Validation failed: Invalid phase marker [$phase] in heading: $line"
                exit 1
            }
        }
    }
}

if ($h1Count -ne 1) {
    Write-Error "Validation failed: Expected exactly 1 # heading, found $h1Count."
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

# --- Write handoff to parent _millhouse/handoff.md (local) ---
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

# --- Write updated tasks.md and commit ---
[System.IO.File]::WriteAllText($TasksPath, $UpdatedTasks, $utf8NoBom)

# Commit and push the tasks.md change (git-tracked)
$TasksRelPath = $TasksPath.Substring($RepoRoot.Length).TrimStart('\', '/')
Push-Location $RepoRoot
try {
    git add $TasksRelPath 2>&1 | Out-Null
    git commit -m "task: claim $TaskTitle for discussing" 2>&1 | Out-Null
    git push 2>&1 | Out-Null
} catch {
    Write-Warning "Git commit/push failed: $_"
}
Pop-Location

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

# --- Create worktree (_millhouse/ will be copied from parent after creation) ---
$spawnArgs = @{
    WorktreeName = $Slug
    BranchName   = $BranchName
    NoOpen       = $true
}

$output = & $WorktreeScript @spawnArgs
$ProjectPath = ($output | Select-Object -Last 1).Trim()
if (-not $ProjectPath -or -not (Test-Path $ProjectPath)) {
    Write-Error "mill-worktree.ps1 did not return a valid project path. Got: '$ProjectPath'"
    exit 1
}

# --- Copy gitignored directories from parent to new worktree ---
# _millhouse/ (excluding scratch/ and children/) — config.yaml is handled by mill-worktree.ps1 but
# other files (handoff, wrappers) need explicit copy.
# .claude/ — not handled by mill-worktree.ps1, needs copy.
# .vscode/ — mill-worktree.ps1 creates its own settings.json, no copy needed.
$srcMillhouse = Join-Path $PWD "_millhouse"
$dstMillhouse = Join-Path $ProjectPath "_millhouse"
if (Test-Path $srcMillhouse) {
    Get-ChildItem $srcMillhouse -Exclude "scratch", "children" | ForEach-Object {
        Copy-Item $_.FullName -Destination (Join-Path $dstMillhouse $_.Name) -Recurse -Force
    }
}

# --- Create empty _millhouse/scratch structure in new worktree ---
New-Item -ItemType Directory -Path (Join-Path $ProjectPath "_millhouse/scratch/reviews") -Force | Out-Null

# --- Locate status-template.md (three-tier resolution) ---
$StatusTemplate = $null

# Tier 1: plugin source (works in millhouse repo)
$t1 = Join-Path $RepoRoot "plugins\mill\templates\status-template.md"
if (Test-Path $t1) { $StatusTemplate = $t1 }

# Tier 2: plugin cache (works in any repo with mill plugin installed)
if (-not $StatusTemplate) {
    $PluginBaseT = Join-Path $env:USERPROFILE ".claude\plugins\cache\millhouse\mill"
    if (Test-Path $PluginBaseT) {
        $VersionDirT = Get-ChildItem $PluginBaseT -Directory |
            Where-Object { $_.Name -match '^\d+\.\d+\.\d+$' } |
            Sort-Object Name -Descending |
            Select-Object -First 1
        if ($VersionDirT) {
            $t2 = Join-Path $VersionDirT.FullName "templates\status-template.md"
            if (Test-Path $t2) { $StatusTemplate = $t2 }
        }
    }
}

# Tier 3: sibling to script's directory
if (-not $StatusTemplate) {
    $t3 = Join-Path (Split-Path $MyInvocation.MyCommand.Path) "templates\status-template.md"
    if (Test-Path $t3) { $StatusTemplate = $t3 }
}

if (-not $StatusTemplate) {
    Write-Error "status-template.md not found. Ensure the mill plugin is installed correctly."
    exit 1
}

# --- Write status.md in new worktree ---
$TimeStamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$statusContent = Get-Content $StatusTemplate -Raw -Encoding UTF8
$statusContent = $statusContent -replace '\{\{task\}\}', $TaskTitle
$statusContent = $statusContent -replace '\{\{phase\}\}', 'discussing'
$statusContent = $statusContent -replace '\{\{parent\}\}', $ParentBranch
$statusContent = $statusContent -replace '\{\{task_description\}\}', $DiscussionSummary
$statusContent = $statusContent -replace '\{\{timeline_entry\}\}', "discussing              $TimeStamp"

$statusPath = Join-Path $ProjectPath "_millhouse" | Join-Path -ChildPath "scratch"
$statusPath = Join-Path $statusPath "status.md"
[System.IO.File]::WriteAllText($statusPath, $statusContent, $utf8NoBom)

# --- Write child registry entry in parent's _millhouse/children/ ---
$childrenDir = Join-Path $PWD "_millhouse/children"
New-Item -ItemType Directory -Path $childrenDir -Force | Out-Null

# $TimeStamp is ISO 8601 (used in YAML frontmatter); $ChildFileTimestamp is filesystem-safe (used in filename).
$ChildFileTimestamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
$ChildFilename = "$ChildFileTimestamp-$Slug.md"
$ChildFilePath = Join-Path $childrenDir $ChildFilename

# Collision handling: append -2, -3, etc. if file exists
if (Test-Path $ChildFilePath) {
    $suffix = 2
    while (Test-Path (Join-Path $childrenDir "$ChildFileTimestamp-$Slug-$suffix.md")) {
        $suffix++
    }
    $ChildFilename = "$ChildFileTimestamp-$Slug-$suffix.md"
    $ChildFilePath = Join-Path $childrenDir $ChildFilename
}

$childContent = @"
---
task: $TaskTitle
branch: $BranchName
status: active
spawned: $TimeStamp
---

## Summary
$DiscussionSummary
"@

[System.IO.File]::WriteAllText($ChildFilePath, $childContent, $utf8NoBom)
Write-Host "Child registry: $ChildFilename"

# --- Open VS Code (only with -VSCode flag) ---
if ($VSCode) {
    Write-Host "Opening VS Code..."
    $codeCmdPath = Get-Command "code.cmd" -ErrorAction SilentlyContinue
    if ($codeCmdPath) {
        & code.cmd $ProjectPath | Out-Null
    } else {
        Write-Warning "code.cmd not found on PATH. Open manually: $ProjectPath"
    }
}

Write-Host ""
Write-Host "Worktree created at $ProjectPath on branch $BranchName"
Write-Host "Task: $TaskTitle"
if ($VSCode) {
    Write-Host "Run mill-start in the new VS Code window to continue planning."
} else {
    Write-Host "Run mill-terminal.ps1 from the parent terminal to open a Claude Code session in the new worktree."
}

# --- Stdout contract: bare project path as the only Write-Output ---
Write-Output $ProjectPath
