"""
core/plan_review_loop.py — State-machine helper for plan-review fan-out (v2 and v3).

v2: fans out N+1 reviewers in parallel — one per batch slice plus one whole-plan reviewer.
v3: fans out N+1 reviewers in parallel — one per card plus one holistic reviewer.

``PlanReviewLoop`` accepts both ``PlanOverview`` (v2) and ``PlanOverviewV3`` (v3)
and determines the overall outcome after each round.

Outcome literals:
  APPROVED            — all slices approved this round
  CONTINUE            — some slices rejected; rounds remain
  BLOCKED_NON_PROGRESS — a requesting slice has identical pushed-back findings
                         as the prior round (design dispute)
  BLOCKED_MAX_ROUNDS  — max rounds exhausted with unresolved rejections
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Verdict = Literal["APPROVE", "REQUEST_CHANGES"]
SliceId = str  # "batch-<slug>", "whole-plan", "card-<N>", or "holistic"
RoundOutcome = Literal["APPROVED", "CONTINUE", "BLOCKED_NON_PROGRESS", "BLOCKED_MAX_ROUNDS"]


@dataclass
class PlanOverview:
    """Minimal plan overview for v2 batch-based plan format.

    Fields
    ------
    batch_slugs:
        Ordered list of batch slugs from the overview frontmatter
        (e.g. ``["core", "tasks-worktree", "backends"]``).
    """
    batch_slugs: list[str]


@dataclass
class PlanOverviewV3:
    """Minimal plan overview for v3 card-based plan format.

    Fields
    ------
    card_numbers:
        Ordered list of card numbers from the Card Index
        (e.g. ``[1, 2, 3, 4, 5]``).
    """
    card_numbers: list[int]


class PlanReviewLoop:
    """Stateful loop helper for parallel plan-review fan-out (v2 and v3).

    v2 (``PlanOverview``): spawns N per-batch reviewers + 1 whole-plan reviewer.
    v3 (``PlanOverviewV3``): spawns N per-card reviewers + 1 holistic reviewer.

    After all results arrive each round, call ``record_round_result()`` to
    advance the state machine.

    Parameters
    ----------
    overview:
        The plan overview. Pass ``PlanOverview`` for v2, ``PlanOverviewV3`` for v3.
    max_rounds:
        Maximum number of rounds (configurable via ``-pr N`` or config).
    """

    def __init__(self, overview: PlanOverview | PlanOverviewV3, max_rounds: int) -> None:
        self.overview = overview
        self.max_rounds = max_rounds
        self.current_round: int = 0
        # None = no prior round data for this slice yet
        self._prev_pushed_back: dict[SliceId, list[str] | None] = {}

    def next_round_plan(self) -> list[SliceId]:
        """Return the list of reviewer slices for the next round.

        v2: returns ``["batch-<slug>", ..., "whole-plan"]``.
        v3: returns ``["card-<N>", ..., "holistic"]``.

        Stale approvals are never carried forward — all slices re-run every round.
        Increments ``self.current_round`` by 1 on each call.
        """
        self.current_round += 1
        if isinstance(self.overview, PlanOverviewV3):
            return [f"card-{n}" for n in self.overview.card_numbers] + ["holistic"]
        return [f"batch-{slug}" for slug in self.overview.batch_slugs] + ["whole-plan"]

    def record_round_result(
        self,
        verdicts: dict[SliceId, Verdict],
        fixer_report_path: Path | None,
    ) -> RoundOutcome:
        """Record verdicts and determine the overall round outcome.

        Parameters
        ----------
        verdicts:
            Mapping of slice_id → verdict for every slice spawned this round.
        fixer_report_path:
            Path to the fixer report written by the orchestrator. Required
            when any slice returns REQUEST_CHANGES.

        Returns
        -------
        RoundOutcome

        Raises
        ------
        ValueError
            If any slice rejected but ``fixer_report_path`` is None.
        """
        # All approve → done
        if all(v == "APPROVE" for v in verdicts.values()):
            return "APPROVED"

        # Some rejected — fixer report is required
        if fixer_report_path is None:
            raise ValueError(
                "fixer_report_path is required when any slice rejects"
            )

        # Parse per-slice pushed-back findings from the fixer report
        pushed_back = _parse_pushed_back(fixer_report_path)

        # Non-progress detection (per plan spec: first match → block immediately)
        for slice_id, verdict in verdicts.items():
            if verdict == "APPROVE":
                # Approving slices are excluded from non-progress comparison;
                # their _prev_pushed_back entry is NOT updated.
                continue

            # REQUEST_CHANGES: compare against prior round
            current_bullets = pushed_back.get(slice_id, [])
            prev = self._prev_pushed_back.get(slice_id)  # None = no prior round
            if prev is not None and prev == current_bullets:
                return "BLOCKED_NON_PROGRESS"
            # Update tracking for this requesting slice
            self._prev_pushed_back[slice_id] = current_bullets

        # No non-progress detected
        if self.current_round < self.max_rounds:
            return "CONTINUE"
        return "BLOCKED_MAX_ROUNDS"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_pushed_back(fixer_report_path: Path) -> dict[SliceId, list[str]]:
    """Parse the ``## Pushed Back`` section of a fixer report.

    Returns a mapping of slice_id → ordered list of finding strings.
    Slices with the sentinel ``(empty — slice approved this round)`` body
    map to an empty list.

    Fixer report format:
    ```markdown
    ## Pushed Back
    ### batch-core
    - Finding 1: ...
    ### whole-plan
    (empty — slice approved this round)
    ```
    """
    text = fixer_report_path.read_text(encoding="utf-8", errors="replace")
    result: dict[SliceId, list[str]] = {}

    # Find ## Pushed Back section
    h2_match = re.search(r"^## Pushed Back\s*$", text, re.MULTILINE)
    if h2_match is None:
        return result

    section = text[h2_match.end():]
    # Stop at the next ## heading (Fixed, or any other section)
    next_h2 = re.search(r"^## ", section, re.MULTILINE)
    if next_h2:
        section = section[:next_h2.start()]

    # Parse ### <slice-id> subsections
    subsection_re = re.compile(r"^### (.+)$", re.MULTILINE)
    matches = list(subsection_re.finditer(section))

    for i, m in enumerate(matches):
        slice_id = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(section)
        body = section[start:end].strip()

        if not body or body.startswith("(empty"):
            result[slice_id] = []
        else:
            # Ordered list of bullet lines (preserve original order)
            bullets = [
                line.strip()
                for line in body.splitlines()
                if line.strip().startswith("- ")
            ]
            result[slice_id] = bullets

    return result
