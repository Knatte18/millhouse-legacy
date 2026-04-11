# Link all millhouse plugins to source, bypassing the plugin cache.
# Uses Windows junctions (no admin required).
# Run from the millhouse repo root.

$SourceDir = Join-Path $PSScriptRoot "plugins"
$CacheDir = Join-Path $env:USERPROFILE ".claude\plugins\cache\millhouse"

if (-not (Test-Path $CacheDir)) {
    Write-Host "Error: Plugin cache not found at $CacheDir"
    Write-Host "Run 'claude plugin marketplace add' and install plugins first (see INSTALL.md step 1)."
    exit 1
}

Get-ChildItem -Path $SourceDir -Directory | ForEach-Object {
    $name = $_.Name
    $target = Join-Path $CacheDir "$name\1.0.0"
    $pluginCacheDir = Join-Path $CacheDir $name

    if (-not (Test-Path $pluginCacheDir)) {
        Write-Host "Skipped (not installed): $name"
        return
    }

    # Check if already a junction
    if (Test-Path $target) {
        $item = Get-Item $target -Force
        if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            $currentTarget = $item.Target
            if ($currentTarget -eq $_.FullName) {
                Write-Host "Already linked: $name"
                return
            }
            # Junction points to wrong target — remove and re-create
            Write-Host "Repairing: $name (was -> $currentTarget)"
            cmd /c "rmdir `"$target`"" | Out-Null
        } else {
            # Backup existing cache
            $backup = "${target}.bak"
            if (Test-Path $backup) { Remove-Item $backup -Recurse -Force }
            Move-Item $target $backup
        }
    }

    # Create junction
    cmd /c "mklink /J `"$target`" `"$($_.FullName)`"" | Out-Null
    Write-Host "Linked: $name"
}

Write-Host ""
Write-Host "Done. Plugin edits are now live immediately."
