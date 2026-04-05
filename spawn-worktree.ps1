# spawn-worktree.ps1 — Create a git worktree with VS Code setup.
# Generic script: no Helm, no kanban, no task management.
# Handles: branch resolution, git worktree add, .env copies,
# .vscode/settings.json (unique title bar color), VS Code launch.
#
# Outputs the worktree path on success (last line of stdout).

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Branch,

    [string]$DirName = "",

    [switch]$NoOpen,

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

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

# Hub detection: bare repo sits as .bare sibling to worktrees
$HubRoot = Split-Path $RepoRoot -Parent
$IsHub = (Test-Path (Join-Path $HubRoot ".bare"))
$WorktreeName = Split-Path $RepoRoot -Leaf

# --- Derive directory name if not provided ---
if (-not $DirName) {
    # Extract last segment of branch name (e.g. "feature/foo" → "foo")
    $BranchLeaf = if ($Branch.Contains('/')) { ($Branch -split '/')[-1] } else { $Branch }

    if ($IsHub -and $WorktreeName -eq "main") {
        # From main worktree in hub: just the branch name
        $DirName = $BranchLeaf
    } elseif ($IsHub) {
        # From a non-main worktree in hub: parent-wt-slug
        $DirName = "$WorktreeName-wt-$BranchLeaf"
    } else {
        # Regular repo: reponame-wt-slug
        $RepoName = $WorktreeName
        $DirName = "$RepoName-wt-$BranchLeaf"
    }
}

if ($IsHub) {
    $WorktreePath = [System.IO.Path]::GetFullPath((Join-Path $HubRoot $DirName))
} else {
    $WorktreePath = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "..\$DirName"))
}

# --- Check path collision ---
if (Test-Path $WorktreePath) {
    Write-Error "Path '$WorktreePath' already exists."
    exit 1
}

# --- Resolve branch ---
$ErrorActionPreference = "Continue"
git rev-parse --verify $Branch 2>$null | Out-Null
$branchExists = ($LASTEXITCODE -eq 0)

$branchCheckedOut = $false
if ($branchExists) {
    $match = git worktree list --porcelain 2>$null | Select-String "^branch refs/heads/$Branch$"
    $branchCheckedOut = ($null -ne $match)
}
$ErrorActionPreference = "Stop"

# Determine the actual branch name and git command
if ($branchExists -and -not $branchCheckedOut) {
    $ActualBranch = $Branch
    $gitArgs = @("worktree", "add", $WorktreePath, $Branch)
} elseif ($branchExists -and $branchCheckedOut) {
    # Branch checked out — derive a new name
    $candidate = "$Branch-wt"
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
        $candidate = "$Branch-wt$n"
        $n++
    }
    $ActualBranch = $candidate
    $gitArgs = @("worktree", "add", $WorktreePath, "-b", $candidate, "HEAD")
} else {
    # Branch does not exist — create it
    $ActualBranch = $Branch
    $gitArgs = @("worktree", "add", $WorktreePath, "-b", $Branch, "HEAD")
}

# --- Pick title bar color ---
$PickedColor = Get-UnusedTitleBarColor

Write-Host "Branch:    $ActualBranch"
Write-Host "Path:      $WorktreePath"
Write-Host "Color:     $PickedColor"

# --- DryRun ---
if ($DryRun) {
    Write-Host ""
    Write-Host "[DryRun] Would create worktree at: $WorktreePath"
    Write-Host "[DryRun] Would use branch: $ActualBranch"
    Write-Host "[DryRun] Would use title bar color: $PickedColor"

    $envFiles = Get-ChildItem -Path $RepoRoot -Filter ".env*" -File -ErrorAction SilentlyContinue
    if ($envFiles) {
        $names = ($envFiles | ForEach-Object { $_.Name }) -join ', '
        Write-Host "[DryRun] Would copy .env files: $names"
    } else {
        Write-Host "[DryRun] No .env files to copy."
    }

    Write-Host "[DryRun] Would write: _git/config.yaml"
    Write-Host "[DryRun] Would write: .vscode/settings.json"
    if (-not $NoOpen) { Write-Host "[DryRun] Would open VS Code." }
    Write-Output $WorktreePath
    exit 0
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

# --- _git/config.yaml ---
$BaseBranch = "main"
$sourceGitConfig = Join-Path $RepoRoot "_git" | Join-Path -ChildPath "config.yaml"
if (Test-Path $sourceGitConfig) {
    foreach ($line in (Get-Content $sourceGitConfig)) {
        if ($line -match '^\s*base-branch:\s*(.+)$') {
            $BaseBranch = $Matches[1].Trim()
        }
    }
}
$gitDir = Join-Path $WorktreePath "_git"
New-Item -ItemType Directory -Path $gitDir -Force | Out-Null
$gitConfigContent = "base-branch: $BaseBranch`nparent-branch: $SourceBranch"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $gitDir "config.yaml"), $gitConfigContent, $utf8NoBom)

# --- Copy .env* files ---
$envFiles = Get-ChildItem -Path $RepoRoot -Filter ".env*" -File -ErrorAction SilentlyContinue
foreach ($f in $envFiles) {
    Copy-Item $f.FullName (Join-Path $WorktreePath $f.Name)
}

# --- .vscode/settings.json ---
$vscodeDir = Join-Path $WorktreePath ".vscode"
New-Item -ItemType Directory -Path $vscodeDir -Force | Out-Null
$settingsJson = @"
{
    "workbench.colorCustomizations": {
        "titleBar.activeBackground": "$PickedColor",
        "titleBar.activeForeground": "#ffffff"
    },
    "window.title": "`${rootName}"
}
"@
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $vscodeDir "settings.json"), $settingsJson, $utf8NoBom)

Write-Host "Title bar color: $PickedColor"

# --- Open VS Code ---
if (-not $NoOpen) {
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
}

Write-Host ""
Write-Host "Worktree ready: $WorktreePath (branch: $ActualBranch)"

# Output path for callers to capture
Write-Output $WorktreePath
