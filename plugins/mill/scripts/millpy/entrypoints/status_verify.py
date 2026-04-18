"""
entrypoints/status_verify.py — Verify status.md against directory state.

Reads the current active task's status.md via .mill/active/<slug>/status.md
and checks whether the recorded phase is consistent with the filesystem state
(presence of discussion.md, plan/ directory, reviews/ files).

Exit codes
----------
0 — consistent (or no active task)
1 — at least one mismatch detected
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def _phase_index(phase: str, ordered: list[str]) -> int:
    """Return the index of the base phase in ``ordered``.

    Strips any trailing ``-r<N>`` or ``-<N>`` suffix before lookup.
    Unrecognized phases return -1 (sort lower than all known phases).
    """
    base = re.sub(r"(-r?\d+)$", "", phase)
    try:
        return ordered.index(base)
    except ValueError:
        return -1


# Base phases in increasing order (placeholders stripped).
_BASE_PHASES: list[str] = [
    "discussing",
    "discussed",
    "planned",
    "implementing",
    "testing",
    "reviewing",
    "blocked",
    "pr-pending",
    "complete",
]


def main(argv: list[str] | None = None) -> int:
    """Verify status.md against directory state.

    Parameters
    ----------
    argv:
        Argument vector. No flags — operates on the current worktree.

    Returns
    -------
    int
        0 if consistent, 1 if mismatches found.
    """
    from millpy.core.config import load_merged
    from millpy.core.paths import (
        active_dir,
        local_config_path,
        mill_junction_path,
        slug_from_branch,
    )
    from millpy.tasks import status_md

    # Load config (best-effort — only needed for slug_from_branch prefix stripping).
    mill = mill_junction_path()
    shared_cfg_path = mill / "config.yaml"
    local_cfg_path = local_config_path()
    cfg = load_merged(shared_cfg_path, local_cfg_path)

    slug = slug_from_branch(cfg)
    task_dir = active_dir(cfg, slug=slug)

    if not task_dir.exists():
        print("no active task")
        return 0

    status_path = task_dir / "status.md"
    if not status_path.exists():
        print(f"no status.md in {task_dir}")
        return 0

    data = status_md.load(status_path)
    phase = str(data.get("phase", "")).strip()

    phase_idx = _phase_index(phase, _BASE_PHASES)

    mismatches: list[str] = []

    # Check: plan/ directory
    plan_present = (task_dir / "plan").exists()
    # planned >= "planned" in order
    planned_idx = _BASE_PHASES.index("planned")
    if plan_present and phase_idx < planned_idx:
        mismatches.append(
            f"phase={phase} but plan/ present (expected phase >= planned)"
        )
    if not plan_present and phase_idx >= _BASE_PHASES.index("complete"):
        mismatches.append(
            f"phase={phase} but plan/ missing"
        )

    # Check: discussion.md
    discussion_present = (task_dir / "discussion.md").exists()
    discussed_idx = _BASE_PHASES.index("discussed")
    if discussion_present and phase_idx < _BASE_PHASES.index("discussing"):
        mismatches.append(
            f"phase={phase} but discussion.md present"
        )
    if not discussion_present and phase_idx >= _BASE_PHASES.index("complete"):
        mismatches.append(
            f"phase={phase} but discussion.md missing"
        )

    # Check: reviews/ files
    reviews_dir = task_dir / "reviews"
    review_files = list(reviews_dir.glob("*-code-review-r*.md")) if reviews_dir.exists() else []
    if review_files:
        reviewing_idx = _BASE_PHASES.index("reviewing")
        if phase_idx < reviewing_idx:
            mismatches.append(
                f"phase={phase} but code-review files present in reviews/"
            )

    if mismatches:
        for msg in mismatches:
            print(msg)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
