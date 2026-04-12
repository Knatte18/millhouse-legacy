# mill-worktree.ps1 — Create a git worktree with millhouse setup.
# Handles: branch resolution, git worktree add, .env copies,
# _millhouse/config.yaml, .vscode/settings.json (unique title bar color),
# VS Code launch. Supports project subdirectories (cwd != git root).
#
# Outputs the project path on success (last line of stdout).
# When cwd is a subdirectory of git root, the project path is the
# corresponding subdirectory within the new worktree.

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$WorktreeName,

    [Parameter(Mandatory)]
    [string]$BranchName,

    # Override: callers may pass DirName to decouple directory name from WorktreeName.
    # If not provided, DirName defaults to WorktreeName.
    [string]$DirName = "",

    [switch]$NoOpen,

    [switch]$Terminal,

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# --- Validate WorktreeName ---
if ($WorktreeName -match '/') {
    Write-Error "WorktreeName must not contain '/'. Got: '$WorktreeName'"
    exit 1
}

# --- Capture source branch (before any worktree operations) ---
$SourceBranch = (git branch --show-current 2>&1).Trim()

# --- Helpers ---

function Get-UnusedTitleBarColor {
    $palette = @('#2d7d46', '#7d2d6b', '#2d4f7d', '#7d5c2d', '#6b2d2d', '#2d6b6b', '#4a2d7d', '#7d462d')
    $usedColors = New-Object System.Collections.ArrayList
    $wtOutput = git worktree list --porcelain 2>$null
    if ($wtOutput) {
        foreach ($line in $wtOutput) {
            if ($line -match '^worktree\s+(.+)$') {
                $wtSettingsPath = Join-Path $Matches[1] ".vscode" | Join-Path -ChildPath "settings.json"
                if (Test-Path $wtSettingsPath) {
                    $json = Get-Content $wtSettingsPath -Raw
                    if ($json -match '"titleBar\.activeBackground"\s*:\s*"(#[0-9a-fA-F]+)"') {
                        [void]$usedColors.Add($Matches[1])
                    }
                }
            }
        }
    }
    foreach ($color in $palette) {
        if ($color -notin $usedColors) {
            return $color
        }
    }
    return $palette[0]
}

# --- Resolve repo root and layout ---
$RepoRoot = (git rev-parse --show-toplevel 2>&1).Trim()
if ($LASTEXITCODE -ne 0) {
    Write-Error "Not in a git repository."
    exit 1
}

# --- Compute project subdirectory offset (cwd relative to git root) ---
$ProjectSubdir = $PWD.Path.Substring($RepoRoot.Length).TrimStart('\', '/')

# Hub detection: bare repo sits as .bare sibling to worktrees
$HubRoot = Split-Path $RepoRoot -Parent
$IsHub = (Test-Path (Join-Path $HubRoot ".bare"))

# --- Derive directory name if not provided ---
if (-not $DirName) {
    $DirName = $WorktreeName
}

if ($IsHub) {
    $WorktreePath = [System.IO.Path]::GetFullPath((Join-Path $HubRoot $DirName))
} else {
    $RepoName = Split-Path $RepoRoot -Leaf
    $WorktreeContainer = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "..\$RepoName.worktrees"))
    $WorktreePath = Join-Path $WorktreeContainer $DirName
}

# Compute project path within the new worktree
$ProjectPath = [System.IO.Path]::GetFullPath((Join-Path $WorktreePath $ProjectSubdir))

# --- Check path collision ---
if (Test-Path $WorktreePath) {
    # Orphan directory from a previous worktree that was not fully cleaned up.
    # Check it is not an active worktree before removing.
    $activeWorktrees = git worktree list --porcelain 2>&1
    $normalizedTarget = $WorktreePath.Replace('\', '/')
    $isActive = $false
    foreach ($line in ($activeWorktrees -split '\r?\n')) {
        if ($line -match '^worktree (.+)$') {
            $wt = $Matches[1].Replace('\', '/')
            if ($wt -eq $normalizedTarget) { $isActive = $true; break }
        }
    }
    if ($isActive) {
        Write-Error "Path '$WorktreePath' is an active worktree. Cannot overwrite."
        exit 1
    }
    Write-Host "Removing orphaned directory: $WorktreePath"
    Remove-Item -Recurse -Force $WorktreePath
}

# --- Resolve branch ---
$ErrorActionPreference = "Continue"
git rev-parse --verify $BranchName 2>$null | Out-Null
$branchExists = ($LASTEXITCODE -eq 0)

$branchCheckedOut = $false
if ($branchExists) {
    $match = git worktree list --porcelain 2>$null | Select-String "^branch refs/heads/$BranchName$"
    $branchCheckedOut = ($null -ne $match)
}
$ErrorActionPreference = "Stop"

# Determine the actual branch name and git command
if ($branchExists -and -not $branchCheckedOut) {
    $ActualBranch = $BranchName
    $gitArgs = @("worktree", "add", $WorktreePath, $BranchName)
} elseif ($branchExists -and $branchCheckedOut) {
    # Branch checked out — derive a new name
    $candidate = "$BranchName-wt"
    $n = 2
    while ($true) {
        $ErrorActionPreference = "Continue"
        git rev-parse --verify $candidate 2>$null | Out-Null
        $candExists = ($LASTEXITCODE -eq 0)
        $candCheckedOut = $false
        if ($candExists) {
            $m = git worktree list --porcelain 2>$null | Select-String "^branch refs/heads/$candidate$"
            $candCheckedOut = ($null -ne $m)
        }
        $ErrorActionPreference = "Stop"
        if (-not $candExists -and -not $candCheckedOut) { break }
        $candidate = "$BranchName-wt$n"
        $n++
    }
    $ActualBranch = $candidate
    $gitArgs = @("worktree", "add", $WorktreePath, "-b", $candidate, "HEAD")
} else {
    # Branch does not exist locally — check remote
    $ActualBranch = $BranchName
    $ErrorActionPreference = "Continue"
    git rev-parse --verify "origin/$BranchName" 2>$null | Out-Null
    $remoteExists = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = "Stop"

    if ($remoteExists) {
        # Create local branch tracking the remote
        $gitArgs = @("worktree", "add", "--track", "-b", $BranchName, $WorktreePath, "origin/$BranchName")
    } else {
        # No local or remote — create new branch from HEAD
        $gitArgs = @("worktree", "add", $WorktreePath, "-b", $BranchName, "HEAD")
    }
}

# --- Pick title bar color ---
$PickedColor = Get-UnusedTitleBarColor

# --- Build window title ---
$ShortName = ""
$configForTitle = Join-Path $PWD "_millhouse" | Join-Path -ChildPath "config.yaml"
if (Test-Path $configForTitle) {
    foreach ($line in (Get-Content $configForTitle -Encoding UTF8)) {
        if ($line -match '^\s*short-name:\s*"?([^"]*)"?\s*$') {
            $ShortName = $Matches[1].Trim()
        }
    }
}

if ($ShortName) {
    $WindowTitle = "$ShortName`: $WorktreeName"
} else {
    $WindowTitle = "`${rootName}"
}

Write-Host "Branch:    $ActualBranch"
Write-Host "Path:      $WorktreePath"
Write-Host "Project:   $ProjectPath"
Write-Host "Color:     $PickedColor"

# --- DryRun ---
if ($DryRun) {
    Write-Host ""
    Write-Host "[DryRun] Would create worktree at: $WorktreePath"
    Write-Host "[DryRun] Would use branch: $ActualBranch"
    Write-Host "[DryRun] Would set up project at: $ProjectPath"
    Write-Host "[DryRun] Would use title bar color: $PickedColor"

    $envFiles = Get-ChildItem -Path $RepoRoot -Filter ".env*" -File -ErrorAction SilentlyContinue
    if ($envFiles) {
        $names = ($envFiles | ForEach-Object { $_.Name }) -join ', '
        Write-Host "[DryRun] Would copy .env files: $names"
    } else {
        Write-Host "[DryRun] No .env files to copy."
    }

    Write-Host "[DryRun] Would write: _millhouse/config.yaml (at $ProjectPath)"
    Write-Host "[DryRun] Would write: .vscode/settings.json (at $ProjectPath)"
    if (-not $NoOpen -and -not $Terminal) { Write-Host "[DryRun] Would open VS Code at: $ProjectPath" }
    Write-Output $ProjectPath
    exit 0
}

# --- Create worktree container directory (non-hub only) ---
if (-not $IsHub) {
    New-Item -ItemType Directory -Path $WorktreeContainer -Force | Out-Null
}

# --- Create worktree ---
Write-Host ""
Write-Host "Creating worktree..."
$ErrorActionPreference = "Continue"
& git @gitArgs 2>&1 | ForEach-Object { Write-Host $_ }
$ErrorActionPreference = "Stop"
if ($LASTEXITCODE -ne 0) {
    Write-Error "git worktree add failed."
    exit 1
}

# --- _millhouse/config.yaml (full config for new worktree) ---
$sourceConfig = Join-Path $PWD "_millhouse" | Join-Path -ChildPath "config.yaml"
$millhouseDir = Join-Path $ProjectPath "_millhouse"
New-Item -ItemType Directory -Path $millhouseDir -Force | Out-Null
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

if (Test-Path $sourceConfig) {
    # Copy source config and update git.parent-branch
    $configContent = Get-Content $sourceConfig -Raw -Encoding UTF8
    $configContent = $configContent -replace '(?m)^(\s*parent-branch:\s*).+$', "`${1}$SourceBranch"
    [System.IO.File]::WriteAllText((Join-Path $millhouseDir "config.yaml"), $configContent, $utf8NoBom)
} else {
    # Write default full config
    $configContent = @"
git:
  base-branch: main
  parent-branch: $SourceBranch
  auto-merge: false
  require-pr-to-base: false

repo:
  short-name: ""
  branch-prefix: ~

reviews:
  discussion: 2
  plan: 3
  code: 3

models:
  session: opus
  plan-review: sonnet
  code-review: sonnet
  plan-fixer: sonnet
  code-fixer: sonnet
  explore: haiku

notifications:
  slack:
    enabled: false
    webhook: ""
    channel: ""
  toast:
    enabled: true
"@
    [System.IO.File]::WriteAllText((Join-Path $millhouseDir "config.yaml"), $configContent, $utf8NoBom)
}

# --- Copy .env* files (to worktree root, not project subdir) ---
$envFiles = Get-ChildItem -Path $RepoRoot -Filter ".env*" -File -ErrorAction SilentlyContinue
foreach ($f in $envFiles) {
    Copy-Item $f.FullName (Join-Path $WorktreePath $f.Name)
}

# --- .vscode/settings.json (at project path) ---
$vscodeDir = Join-Path $ProjectPath ".vscode"
New-Item -ItemType Directory -Path $vscodeDir -Force | Out-Null
$settingsJson = @"
{
    "workbench.colorCustomizations": {
        "titleBar.activeBackground": "$PickedColor",
        "titleBar.activeForeground": "#ffffff",
        "titleBar.inactiveBackground": "$PickedColor",
        "titleBar.inactiveForeground": "#ffffffaa"
    },
    "window.title": "$WindowTitle"
}
"@
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $vscodeDir "settings.json"), $settingsJson, $utf8NoBom)

Write-Host "Title bar color: $PickedColor"

# --- .vscode/tasks.json (at parent's project path, i.e. $PWD) ---
$parentVscodeDir = Join-Path $PWD ".vscode"
$parentTasksJsonPath = Join-Path $parentVscodeDir "tasks.json"

# Resolve mill-terminal.ps1 path (same directory as this script)
$terminalScript = Join-Path (Split-Path $MyInvocation.MyCommand.Path) "mill-terminal.ps1"

$millTaskObj = @"
        {
            "label": "Mill: Open Terminal Session",
            "type": "shell",
            "command": "& '$terminalScript'",
            "presentation": {
                "group": "mill"
            }
        }
"@

if (Test-Path $parentTasksJsonPath) {
    # Parse existing tasks.json and append if Mill task not present
    try {
        $existingJson = Get-Content $parentTasksJsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $hasMillTask = $false
        if ($existingJson.tasks) {
            foreach ($t in $existingJson.tasks) {
                if ($t.label -eq "Mill: Open Terminal Session") {
                    $hasMillTask = $true
                    break
                }
            }
        }
        if (-not $hasMillTask) {
            if (-not $existingJson.tasks) {
                $existingJson | Add-Member -NotePropertyName "tasks" -NotePropertyValue @()
            }
            $newTask = @{
                label = "Mill: Open Terminal Session"
                type = "shell"
                command = "& '$terminalScript'"
                presentation = @{ group = "mill" }
            }
            $existingJson.tasks += $newTask
            $updatedJson = $existingJson | ConvertTo-Json -Depth 10
            [System.IO.File]::WriteAllText($parentTasksJsonPath, $updatedJson, $utf8NoBom)
            Write-Host "Added Mill terminal task to existing .vscode/tasks.json"
        }
    } catch {
        Write-Warning ".vscode/tasks.json exists but could not be parsed — skipping Mill task registration."
    }
} else {
    # Create new tasks.json with Mill task
    New-Item -ItemType Directory -Path $parentVscodeDir -Force | Out-Null
    $tasksJsonContent = @"
{
    "version": "2.0.0",
    "tasks": [
$millTaskObj
    ]
}
"@
    [System.IO.File]::WriteAllText($parentTasksJsonPath, $tasksJsonContent, $utf8NoBom)
    Write-Host "Created .vscode/tasks.json with Mill terminal task"
}

# --- Open VS Code (at project path) ---
if (-not $NoOpen -and -not $Terminal) {
    Write-Host "Opening VS Code..."
    $codeCmdPath = Get-Command "code.cmd" -ErrorAction SilentlyContinue
    if ($codeCmdPath) {
        & code.cmd $ProjectPath
    } else {
        $fallback = Join-Path $env:LOCALAPPDATA "Programs\Microsoft VS Code\bin\code.cmd"
        if (Test-Path $fallback) {
            & $fallback $ProjectPath
        } else {
            Write-Warning "code.cmd not found. Open manually: $ProjectPath"
        }
    }
}

Write-Host ""
Write-Host "Worktree ready: $ProjectPath (branch: $ActualBranch)"

# Output project path for callers to capture
Write-Output $ProjectPath
