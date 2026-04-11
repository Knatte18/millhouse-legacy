# mill-vscode.ps1 — Open VS Code in a child worktree.
# Scans _millhouse/children/ for active entries, presents a picker if
# multiple, then opens VS Code in the selected worktree.
#
# Run from the parent worktree (main repo).

$ErrorActionPreference = "Stop"

# --- Resolve children directory ---
$ChildrenDir = Join-Path $PWD "_millhouse/children"
if (-not (Test-Path $ChildrenDir)) {
    Write-Host "No _millhouse/children/ directory found. No spawned worktrees."
    exit 0
}

$childFiles = Get-ChildItem $ChildrenDir -Filter "*.md" -File -ErrorAction SilentlyContinue
if (-not $childFiles -or $childFiles.Count -eq 0) {
    Write-Host "No child registry entries found."
    exit 0
}

# --- Parse active children ---
$activeChildren = @()

# Build worktree lookup: branch -> path
$wtLookup = @{}
$wtOutput = git worktree list --porcelain 2>$null
$currentWtPath = $null
foreach ($line in ($wtOutput -split '\r?\n')) {
    if ($line -match '^worktree\s+(.+)$') {
        $currentWtPath = $Matches[1]
    }
    if ($line -match '^branch\s+refs/heads/(.+)$' -and $currentWtPath) {
        $wtLookup[$Matches[1]] = $currentWtPath
    }
}

foreach ($file in $childFiles) {
    $content = Get-Content $file.FullName -Raw -Encoding UTF8
    # Parse YAML frontmatter
    if ($content -match '(?s)^---\s*\r?\n(.+?)\r?\n---') {
        $yaml = $Matches[1]
        $status = ""
        $task = ""
        $branch = ""
        foreach ($yline in ($yaml -split '\r?\n')) {
            if ($yline -match '^\s*status:\s*(.+)$') { $status = $Matches[1].Trim() }
            if ($yline -match '^\s*task:\s*(.+)$') { $task = $Matches[1].Trim() }
            if ($yline -match '^\s*branch:\s*(.+)$') { $branch = $Matches[1].Trim() }
        }
        if ($status -eq 'active' -and $task -and $branch) {
            $wtPath = $wtLookup[$branch]
            if ($wtPath) {
                $activeChildren += @{
                    Task   = $task
                    Branch = $branch
                    Path   = $wtPath
                    File   = $file.Name
                }
            } else {
                Write-Host "Worktree for '$task' not found (branch: $branch). It may have been cleaned up."
            }
        }
    }
}

if ($activeChildren.Count -eq 0) {
    Write-Host "No active child worktrees found."
    exit 0
}

# --- Select child ---
$selected = $null
if ($activeChildren.Count -eq 1) {
    $selected = $activeChildren[0]
    Write-Host "Auto-selecting: $($selected.Task) ($($selected.Branch))"
} else {
    Write-Host "Active worktrees:"
    Write-Host ""
    for ($i = 0; $i -lt $activeChildren.Count; $i++) {
        $c = $activeChildren[$i]
        Write-Host "  $($i + 1)) $($c.Task)  ($($c.Branch))"
    }
    Write-Host ""
    $choice = Read-Host "Select worktree (1-$($activeChildren.Count))"
    $num = 0
    if (-not [int]::TryParse($choice, [ref]$num) -or $num -lt 1 -or $num -gt $activeChildren.Count) {
        Write-Error "Invalid selection: $choice"
        exit 1
    }
    $selected = $activeChildren[$num - 1]
}

# --- Open VS Code ---
Write-Host ""
Write-Host "Opening VS Code in: $($selected.Path)"
Write-Host ""

$codeCmdPath = Get-Command "code.cmd" -ErrorAction SilentlyContinue
if ($codeCmdPath) {
    & code.cmd $selected.Path
} else {
    $fallback = Join-Path $env:LOCALAPPDATA "Programs\Microsoft VS Code\bin\code.cmd"
    if (Test-Path $fallback) {
        & $fallback $selected.Path
    } else {
        Write-Warning "code.cmd not found. Open manually: $($selected.Path)"
    }
}
