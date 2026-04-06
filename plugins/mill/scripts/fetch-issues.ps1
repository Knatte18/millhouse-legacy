# fetch-issues.ps1 — Fetch open GitHub issues for the current repo.
# Writes structured JSON to _millhouse/scratch/issues.json.
#
# Outputs the issues.json path on success (last line of stdout).

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# --- Detect repository ---
$Repo = ""
try {
    $Repo = (gh repo view --json nameWithOwner -q .nameWithOwner 2>&1).Trim()
} catch {}

if (-not $Repo) {
    $RemoteUrl = ""
    try {
        $RemoteUrl = (git remote get-url origin 2>&1).Trim()
    } catch {}

    if ($RemoteUrl -match '^https://github\.com/(.+?)(?:\.git)?$') {
        $Repo = $Matches[1]
    } elseif ($RemoteUrl -match '^git@github\.com:(.+?)(?:\.git)?$') {
        $Repo = $Matches[1]
    }
}

if (-not $Repo) {
    Write-Error "Could not detect the repository. Are you in a git repo with a GitHub remote?"
    exit 1
}

# --- Fetch open issues ---
$IssuesJson = gh issue list --repo $Repo --state open --json number,title,body,labels,createdAt --limit 100 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "gh issue list failed: $IssuesJson"
    exit 1
}

# --- Build output ---
$FetchedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$Output = @{
    repo      = $Repo
    fetchedAt = $FetchedAt
    issues    = ($IssuesJson | ConvertFrom-Json)
} | ConvertTo-Json -Depth 5

# --- Write to file (cwd-relative) ---
$OutDir = Join-Path $PWD "_millhouse" | Join-Path -ChildPath "scratch"
if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}
$OutFile = Join-Path $OutDir "issues.json"
$Output | Out-File -FilePath $OutFile -Encoding utf8

# --- Stdout contract ---
Write-Output $OutFile
