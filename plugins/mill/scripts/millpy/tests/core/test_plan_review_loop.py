"""
test_plan_review_loop.py — Unit tests for core.plan_review_loop.PlanReviewLoop.

Covers all 7 plan-spec scenarios, including the Scenario 7 critical regression
test for the approving-slice non-progress guard.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from millpy.core.plan_review_loop import PlanOverview, PlanReviewLoop


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(dir_path: Path, filename: str, pushed_back: dict[str, list[str]]) -> Path:
    """Write a fixer report with ## Pushed Back + ### <slice-id> subsections."""
    dir_path.mkdir(parents=True, exist_ok=True)
    lines: list[str] = ["## Pushed Back\n"]
    for slice_id, findings in pushed_back.items():
        lines.append(f"### {slice_id}\n")
        if findings:
            for finding in findings:
                lines.append(f"{finding}\n")
        else:
            lines.append("(empty — slice approved this round)\n")
    p = dir_path / filename
    p.write_text("".join(lines), encoding="utf-8")
    return p


def _make_loop(slugs: list[str] | None = None, max_rounds: int = 3) -> PlanReviewLoop:
    if slugs is None:
        slugs = ["core", "extras"]
    return PlanReviewLoop(PlanOverview(batch_slugs=slugs), max_rounds=max_rounds)


# ---------------------------------------------------------------------------
# Scenario 1: all slices approve on round 1 → APPROVED
# ---------------------------------------------------------------------------

class TestScenario1AllApproveRound1:
    def test_all_approve_returns_approved(self):
        loop = _make_loop()
        slices = loop.next_round_plan()
        assert slices == ["batch-core", "batch-extras", "whole-plan"]
        assert loop.current_round == 1

        verdicts = {s: "APPROVE" for s in slices}
        outcome = loop.record_round_result(verdicts, fixer_report_path=None)
        assert outcome == "APPROVED"


# ---------------------------------------------------------------------------
# Scenario 2: mixed round 1 → CONTINUE; all approve round 2 → APPROVED
# ---------------------------------------------------------------------------

class TestScenario2MixedThenAllApprove:
    def test_continue_then_approved(self, tmp_path: Path):
        loop = _make_loop()
        loop.next_round_plan()

        report = _make_report(tmp_path, "fix_r1.md", {
            "batch-core": [],
            "batch-extras": ["- Finding 1: missing Reads"],
            "whole-plan": [],
        })
        verdicts_r1 = {
            "batch-core": "APPROVE",
            "batch-extras": "REQUEST_CHANGES",
            "whole-plan": "APPROVE",
        }
        outcome1 = loop.record_round_result(verdicts_r1, report)
        assert outcome1 == "CONTINUE"

        slices2 = loop.next_round_plan()
        assert loop.current_round == 2
        verdicts_r2 = {s: "APPROVE" for s in slices2}
        outcome2 = loop.record_round_result(verdicts_r2, fixer_report_path=None)
        assert outcome2 == "APPROVED"


# ---------------------------------------------------------------------------
# Scenario 3: identical pushed-back in consecutive rounds → BLOCKED_NON_PROGRESS
# ---------------------------------------------------------------------------

class TestScenario3NonProgressDetection:
    def test_identical_findings_returns_blocked_non_progress(self, tmp_path: Path):
        loop = _make_loop()
        finding = "- Finding 1: design dispute"

        loop.next_round_plan()
        report1 = _make_report(tmp_path / "r1", "fix.md", {
            "batch-core": [],
            "batch-extras": [finding],
            "whole-plan": [],
        })
        verdicts_r1 = {
            "batch-core": "APPROVE",
            "batch-extras": "REQUEST_CHANGES",
            "whole-plan": "APPROVE",
        }
        outcome1 = loop.record_round_result(verdicts_r1, report1)
        assert outcome1 == "CONTINUE"

        loop.next_round_plan()
        report2 = _make_report(tmp_path / "r2", "fix.md", {
            "batch-core": [],
            "batch-extras": [finding],
            "whole-plan": [],
        })
        verdicts_r2 = {
            "batch-core": "APPROVE",
            "batch-extras": "REQUEST_CHANGES",
            "whole-plan": "APPROVE",
        }
        outcome2 = loop.record_round_result(verdicts_r2, report2)
        assert outcome2 == "BLOCKED_NON_PROGRESS"


# ---------------------------------------------------------------------------
# Scenario 4: max rounds exhausted → BLOCKED_MAX_ROUNDS
# ---------------------------------------------------------------------------

class TestScenario4MaxRoundsExhausted:
    def test_max_rounds_returns_blocked_max_rounds(self, tmp_path: Path):
        loop = _make_loop(max_rounds=2)

        loop.next_round_plan()
        report1 = _make_report(tmp_path / "r1", "fix.md", {
            "batch-extras": ["- Finding 1: problem A"],
        })
        verdicts_r1 = {
            "batch-core": "APPROVE",
            "batch-extras": "REQUEST_CHANGES",
            "whole-plan": "APPROVE",
        }
        outcome1 = loop.record_round_result(verdicts_r1, report1)
        assert outcome1 == "CONTINUE"

        loop.next_round_plan()
        assert loop.current_round == 2
        report2 = _make_report(tmp_path / "r2", "fix.md", {
            "batch-extras": ["- Finding 1: problem B"],  # different finding — no non-progress
        })
        verdicts_r2 = {
            "batch-core": "APPROVE",
            "batch-extras": "REQUEST_CHANGES",
            "whole-plan": "APPROVE",
        }
        outcome2 = loop.record_round_result(verdicts_r2, report2)
        assert outcome2 == "BLOCKED_MAX_ROUNDS"


# ---------------------------------------------------------------------------
# Scenario 5: slice flips REQUEST_CHANGES → APPROVE; other slice still fires
# ---------------------------------------------------------------------------

class TestScenario5SliceFlipsToApprove:
    def test_flipped_slice_does_not_suppress_other_non_progress(self, tmp_path: Path):
        """Slice that flips to APPROVE is excluded; batch-tasks non-progress still fires."""
        loop = _make_loop(slugs=["core", "tasks"])
        finding = "- Finding 1: still failing"

        loop.next_round_plan()
        report1 = _make_report(tmp_path / "r1", "fix.md", {
            "batch-core": ["- Finding 0: core issue"],
            "batch-tasks": [finding],
            "whole-plan": [],
        })
        verdicts_r1 = {
            "batch-core": "REQUEST_CHANGES",
            "batch-tasks": "REQUEST_CHANGES",
            "whole-plan": "APPROVE",
        }
        outcome1 = loop.record_round_result(verdicts_r1, report1)
        assert outcome1 == "CONTINUE"

        loop.next_round_plan()
        report2 = _make_report(tmp_path / "r2", "fix.md", {
            "batch-core": [],
            "batch-tasks": [finding],
            "whole-plan": [],
        })
        verdicts_r2 = {
            "batch-core": "APPROVE",
            "batch-tasks": "REQUEST_CHANGES",
            "whole-plan": "APPROVE",
        }
        outcome2 = loop.record_round_result(verdicts_r2, report2)
        assert outcome2 == "BLOCKED_NON_PROGRESS"


# ---------------------------------------------------------------------------
# Scenario 6: first rejection of a slice has no prior → CONTINUE (not non-progress)
# ---------------------------------------------------------------------------

class TestScenario6FirstRoundRequestChanges:
    def test_first_reject_returns_continue_not_non_progress(self, tmp_path: Path):
        """First rejection has no prior entry → non-progress cannot fire."""
        loop = _make_loop()
        loop.next_round_plan()
        report = _make_report(tmp_path, "fix_r1.md", {
            "batch-extras": ["- Finding 1: issue A"],
            "whole-plan": [],
        })
        verdicts = {
            "batch-core": "APPROVE",
            "batch-extras": "REQUEST_CHANGES",
            "whole-plan": "APPROVE",
        }
        outcome = loop.record_round_result(verdicts, report)
        assert outcome == "CONTINUE"


# ---------------------------------------------------------------------------
# Scenario 7 (CRITICAL REGRESSION): approving slice with prior pushed-back
# entry does NOT trigger BLOCKED_NON_PROGRESS
# ---------------------------------------------------------------------------

class TestScenario7ApprovingSliceWithPriorEntryDoesNotFireNonProgress:
    def test_approving_slice_excluded_from_non_progress_comparison(self, tmp_path: Path):
        """
        Scenario 7: batch-core approved in both rounds. Its empty pushed-back
        entry in _prev_pushed_back must NOT cause a false-positive
        BLOCKED_NON_PROGRESS. Only batch-tasks (which rejects in both rounds
        with identical findings) should trigger BLOCKED_NON_PROGRESS.
        """
        loop = _make_loop(slugs=["core", "tasks"])

        # Round 1: core rejects with empty findings; tasks rejects with Finding 1
        loop.next_round_plan()
        report1 = _make_report(tmp_path / "r1", "fix.md", {
            "batch-core": [],                              # empty pushed-back for core
            "batch-tasks": ["- Finding 1: persistent issue"],
            "whole-plan": [],
        })
        verdicts_r1 = {
            "batch-core": "REQUEST_CHANGES",
            "batch-tasks": "REQUEST_CHANGES",
            "whole-plan": "APPROVE",
        }
        outcome1 = loop.record_round_result(verdicts_r1, report1)
        assert outcome1 == "CONTINUE"
        # _prev_pushed_back now: {"batch-core": [], "batch-tasks": ["- Finding 1: ..."]}

        # Round 2: batch-core FLIPS to APPROVE; batch-tasks still rejects with same Finding 1
        loop.next_round_plan()
        report2 = _make_report(tmp_path / "r2", "fix.md", {
            "batch-core": [],                              # still empty in fixer report
            "batch-tasks": ["- Finding 1: persistent issue"],
            "whole-plan": [],
        })
        verdicts_r2 = {
            "batch-core": "APPROVE",        # flipped — EXCLUDED from non-progress check
            "batch-tasks": "REQUEST_CHANGES",
            "whole-plan": "APPROVE",
        }
        outcome2 = loop.record_round_result(verdicts_r2, report2)
        # batch-tasks fires non-progress (correct)
        # batch-core does NOT fire non-progress despite prev=[] and current=[] (correct)
        assert outcome2 == "BLOCKED_NON_PROGRESS"


# ---------------------------------------------------------------------------
# Edge case: missing fixer_report_path raises ValueError
# ---------------------------------------------------------------------------

class TestMissingFixerReportPath:
    def test_raises_value_error_when_rejections_but_no_report(self):
        loop = _make_loop()
        loop.next_round_plan()
        verdicts = {
            "batch-core": "APPROVE",
            "batch-extras": "REQUEST_CHANGES",
            "whole-plan": "APPROVE",
        }
        with pytest.raises(ValueError, match="fixer_report_path"):
            loop.record_round_result(verdicts, fixer_report_path=None)
