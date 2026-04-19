"""
entrypoints/fetch_issues.py — GitHub issues fetcher for millpy (live).

Fetches open GitHub issues and writes them to .millhouse/scratch/issues.json.

Live after W1 Step 10 skill-text flip: called directly by the mill-inbox
skill via `.millhouse/fetch-issues.py` or direct plugin-source resolution.
"""
from __future__ import annotations

from . import _bootstrap  # noqa: F401

import datetime
import json
import sys


def main(argv: list[str] | None = None) -> int:
    """Fetch open GitHub issues and write to .millhouse/scratch/issues.json.

    Parameters
    ----------
    argv:
        Argument vector (unused — no CLI args for this entry).

    Returns
    -------
    int
        Exit code. Emits the issues.json path as the last stdout line (parity
        with PS1).
    """
    from millpy.core.log_util import log
    from millpy.core.paths import project_root
    from millpy.core.subprocess_util import run as subprocess_run

    try:
        root = project_root()
    except Exception as exc:
        print(f"[fetch_issues] Not in a git repository: {exc}", file=sys.stderr)
        return 1

    # Detect repository
    repo_name = _detect_repo(subprocess_run)
    if not repo_name:
        print(
            "[fetch_issues] Could not detect the repository. "
            "Are you in a git repo with a GitHub remote?",
            file=sys.stderr,
        )
        return 1

    log("fetch_issues", f"repo={repo_name}")

    # Fetch open issues via gh CLI
    result = subprocess_run(
        [
            "gh", "issue", "list",
            "--repo", repo_name,
            "--state", "open",
            "--json", "number,title,body,labels,createdAt",
            "--limit", "100",
        ]
    )

    if result.returncode != 0:
        print(f"[fetch_issues] gh issue list failed: {result.stderr}", file=sys.stderr)
        return 1

    try:
        issues = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"[fetch_issues] Failed to parse gh output: {exc}", file=sys.stderr)
        return 1

    # Build output
    fetched_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output = {
        "repo": repo_name,
        "fetchedAt": fetched_at,
        "issues": issues,
    }

    # Write to .millhouse/scratch/issues.json
    out_dir = root / ".millhouse" / "scratch"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "issues.json"

    out_file.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log("fetch_issues", f"wrote {len(issues)} issues to {out_file}")

    # Emit path as last stdout line (parity with PS1)
    print(str(out_file))
    return 0


def _detect_repo(run) -> str:
    """Detect the GitHub repo name (owner/repo) via gh or git remote.

    Parameters
    ----------
    run:
        subprocess_util.run function.

    Returns
    -------
    str
        "owner/repo" string, or empty string on failure.
    """
    import re

    # Try gh first
    result = run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()

    # Fall back to git remote
    result = run(["git", "remote", "get-url", "origin"])
    if result.returncode == 0:
        url = result.stdout.strip()
        m = re.match(r"^https://github\.com/(.+?)(?:\.git)?$", url)
        if m:
            return m.group(1)
        m = re.match(r"^git@github\.com:(.+?)(?:\.git)?$", url)
        if m:
            return m.group(1)

    return ""


if __name__ == "__main__":
    sys.exit(main())
