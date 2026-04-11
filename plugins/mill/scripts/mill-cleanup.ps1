# mill-cleanup.ps1 — Clean up merged worktrees.
# Scans _millhouse/children/ for merged entries, prints time reports,
# removes tasks from tasks.md, deletes worktrees/branches, cleans up
# child registry entries, commits and pushes tasks.md.
#
# Run from the parent worktree (main repo).

$ErrorActionPreference = "Stop"

# --- Resolve repo root ---
$RepoRoot = (git rev-parse --show-toplevel 2>&1).Trim()
if ($LASTEXITCODE -ne 0) {
    Write-Error "Not in a git repository."
    exit 1
}

# --- Read children registry ---
$ChildrenDir = Join-Path $PWD "_millhouse/children"
if (-not (Test-Path $ChildrenDir)) {
    Write-Host "No _millhouse/children/ directory found. Nothing to clean up."
    exit 0
}

$childFiles = Get-ChildItem $ChildrenDir -Filter "*.md" -File -ErrorAction SilentlyContinue
if (-not $childFiles -or $childFiles.Count -eq 0) {
    Write-Host "No child registry entries found. Nothing to clean up."
    exit 0
}

# --- Build worktree lookup: branch -> path ---
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

# --- Find merged children ---
$mergedChildren = @()
foreach ($file in $childFiles) {
    $content = Get-Content $file.FullName -Raw -Encoding UTF8
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
        if (($status -eq 'merged' -or $status -eq 'complete') -and $task -and $branch) {
            $mergedChildren += @{
                Task   = $task
                Branch = $branch
                Path   = $wtLookup[$branch]
                File   = $file.FullName
            }
        }
    }
}

if ($mergedChildren.Count -eq 0) {
    Write-Host "No merged worktrees to clean up."
    exit 0
}

Write-Host "Found $($mergedChildren.Count) merged worktree(s) to clean up."
Write-Host ""

# --- Read tasks.md (project root) ---
$TasksPath = Join-Path $PWD "tasks.md"
$TasksContent = ""
$tasksChanged = $false
if (Test-Path $TasksPath) {
    $TasksContent = Get-Content $TasksPath -Raw -Encoding UTF8
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$failures = @()

foreach ($child in $mergedChildren) {
    Write-Host "=== Cleaning up: $($child.Task) ==="
    Write-Host "    Branch: $($child.Branch)"

    # --- Time report ---
    if ($child.Path) {
        $statusPath = Join-Path $child.Path "_millhouse/scratch/status.md"
        if (Test-Path $statusPath) {
            $statusContent = Get-Content $statusPath -Raw -Encoding UTF8
            # Parse ## Timeline section
            if ($statusContent -match '(?s)## Timeline\s*\r?\n(.+?)(?:\r?\n##|\z)') {
                $timelineText = $Matches[1].Trim()
                $timelineLines = $timelineText -split '\r?\n' | Where-Object { $_.Trim() -ne '' }

                $entries = @()
                foreach ($tl in $timelineLines) {
                    if ($tl -match '^\s*(\S+)\s+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\s*$') {
                        $entries += @{
                            Phase     = $Matches[1]
                            Timestamp = [DateTime]::Parse($Matches[2])
                        }
                    }
                }

                if ($entries.Count -gt 0) {
                    Write-Host ""
                    Write-Host "    Time Report:"
                    Write-Host "    $('-' * 50)"
                    Write-Host ("    {0,-20} {1,-22} {2}" -f "Phase", "Started", "Duration")
                    Write-Host "    $('-' * 50)"
                    for ($i = 0; $i -lt $entries.Count; $i++) {
                        $e = $entries[$i]
                        $startStr = $e.Timestamp.ToString("yyyy-MM-dd HH:mm:ss")
                        if ($i -lt $entries.Count - 1) {
                            $duration = $entries[$i + 1].Timestamp - $e.Timestamp
                            $durStr = "{0:d}h {1:d2}m" -f [int][Math]::Floor($duration.TotalHours), $duration.Minutes
                        } else {
                            $durStr = "(final)"
                        }
                        Write-Host ("    {0,-20} {1,-22} {2}" -f $e.Phase, $startStr, $durStr)
                    }
                    $totalDuration = $entries[-1].Timestamp - $entries[0].Timestamp
                    $totalStr = "{0:d}h {1:d2}m" -f [int][Math]::Floor($totalDuration.TotalHours), $totalDuration.Minutes
                    Write-Host "    $('-' * 50)"
                    Write-Host "    Total elapsed: $totalStr"
                    Write-Host ""
                }
            } else {
                Write-Host "    No timeline data available."
            }
        } else {
            Write-Host "    No timeline data available (status.md not found)."
        }
    } else {
        Write-Host "    No timeline data available (worktree not found)."
    }

    # --- Remove task from tasks.md ---
    if ($TasksContent) {
        # Match ## [done] <Title> or ## <Title> (with any phase marker)
        $escapedTitle = [regex]::Escape($child.Task)
        $taskHeadingRegex = [regex]::new("(?m)^## (\[[^\]]+\] )?$escapedTitle\s*$")
        $taskMatch = $taskHeadingRegex.Match($TasksContent)
        if ($taskMatch.Success) {
            $blockStart = $taskMatch.Index
            $h2Regex = [regex]::new('(?m)^## ')
            $nextH2 = $h2Regex.Match($TasksContent, $blockStart + $taskMatch.Length)
            if ($nextH2.Success) {
                $blockEnd = $nextH2.Index
            } else {
                $blockEnd = $TasksContent.Length
            }
            $TasksContent = $TasksContent.Substring(0, $blockStart) + $TasksContent.Substring($blockEnd)
            $TasksContent = $TasksContent -replace '(\r?\n){3,}', "`n`n"
            $tasksChanged = $true
            Write-Host "    Removed task from tasks.md."
        } else {
            Write-Host "    Task not found in tasks.md (may have been removed already)."
        }
    }

    # --- Remove worktree ---
    if ($child.Path) {
        try {
            git worktree remove $child.Path 2>&1 | Out-Null
            Write-Host "    Removed worktree: $($child.Path)"
        } catch {
            try {
                git worktree remove $child.Path --force 2>&1 | Out-Null
                Write-Host "    Removed worktree (forced): $($child.Path)"
            } catch {
                $failures += "Failed to remove worktree $($child.Path): $_"
                Write-Warning "    Could not remove worktree: $_"
            }
        }
    }

    # --- Delete local branch ---
    try {
        $ErrorActionPreference = "Continue"
        git branch -D $child.Branch 2>&1 | Out-Null
        Write-Host "    Deleted branch: $($child.Branch)"
        $ErrorActionPreference = "Stop"
    } catch {
        Write-Host "    Branch $($child.Branch) not found (may have been deleted already)."
        $ErrorActionPreference = "Stop"
    }

    # --- Delete checkpoint branch ---
    $checkpointBranch = "mill-checkpoint-$($child.Branch -replace '/', '-')"
    $ErrorActionPreference = "Continue"
    git branch -D $checkpointBranch 2>$null | Out-Null
    $ErrorActionPreference = "Stop"

    # --- Delete remote branch ---
    $ErrorActionPreference = "Continue"
    git push origin --delete $child.Branch 2>$null | Out-Null
    $ErrorActionPreference = "Stop"

    # --- Remove child registry file ---
    if (Test-Path $child.File) {
        Remove-Item $child.File -Force
        Write-Host "    Removed registry: $(Split-Path $child.File -Leaf)"
    }

    Write-Host ""
}

# --- Commit tasks.md changes ---
if ($tasksChanged -and (Test-Path $TasksPath)) {
    [System.IO.File]::WriteAllText($TasksPath, $TasksContent, $utf8NoBom)

    $TasksRelPath = $TasksPath.Substring($RepoRoot.Length).TrimStart('\', '/')
    Push-Location $RepoRoot
    try {
        git add $TasksRelPath 2>&1 | Out-Null
        git commit -m "task: remove completed tasks from tasks.md" 2>&1 | Out-Null
        git push 2>&1 | Out-Null
        Write-Host "Committed and pushed tasks.md changes."
    } catch {
        Write-Warning "Git commit/push for tasks.md failed: $_"
    }
    Pop-Location
}

# --- Prune stale worktree references ---
git worktree prune 2>$null

# --- Summary ---
Write-Host "Cleanup complete. Processed $($mergedChildren.Count) worktree(s)."
if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "Failures:"
    foreach ($f in $failures) {
        Write-Host "  - $f"
    }
}
