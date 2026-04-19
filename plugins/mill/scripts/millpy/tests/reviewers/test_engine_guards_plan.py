"""
test_engine_guards_plan.py — Tests for engine._guard_plan_whole_bulk.

Four scenarios:
1. Bulk SingleWorker + plan phase + plan_dir_path set → guard passes (holistic allowed)
2. Bulk ClusterReviewer + plan phase + plan_dir_path set → guard passes (holistic allowed)
3. Tool-use SingleWorker + plan phase + plan_dir_path set → passes (no error)
4. Bulk SingleWorker + plan phase + plan_dir_path=None → passes (no error)
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


from millpy.reviewers.base import ReviewerResult


def _make_fake_single_worker_class():
    class FakeSW:
        def __init__(self, worker):
            self.worker = worker

        def run(self, **kw):
            kw["review_file_path"].write_text("VERDICT: APPROVE\n", encoding="utf-8")
            return ReviewerResult(
                verdict="APPROVE",
                review_file=kw["review_file_path"],
                exit_code=0,
                failure_kind=None,
            )
    return FakeSW


def _make_fake_ensemble_reviewer_class():
    class FakeER:
        def __init__(self, ensemble):
            self.ensemble = ensemble

        def run(self, **kw):
            kw["review_file_path"].write_text("VERDICT: APPROVE\n", encoding="utf-8")
            return ReviewerResult(
                verdict="APPROVE",
                review_file=kw["review_file_path"],
                exit_code=0,
                failure_kind=None,
            )
    return FakeER


class TestGuardPlanWholeBulk:
    def test_bulk_single_worker_allowed_with_plan_dir(self, tmp_path: Path):
        """Scenario 1: bulk SingleWorker + plan + plan_dir_path → guard passes (holistic allowed)."""
        FakeSW = _make_fake_single_worker_class()
        with (
            patch("millpy.reviewers.engine.project_root", return_value=tmp_path),
            patch("millpy.reviewers.engine.SingleWorker", FakeSW),
        ):
            from millpy.reviewers.engine import run_reviewer
            prompt_file = tmp_path / "prompt.md"
            prompt_file.write_text("p\n", encoding="utf-8")
            result = run_reviewer(
                reviewer_name="g3pro",
                prompt_file=prompt_file,
                phase="plan",
                round=1,
                review_file_path=tmp_path / "out.md",
                plan_start_hash=None,
                plan_path=None,
                files_from=None,
                plan_dir_path=tmp_path / "plan",
            )
        assert result.verdict == "APPROVE"

    def test_bulk_ensemble_allowed_with_plan_dir(self, tmp_path: Path):
        """Scenario 2: bulk ClusterReviewer + plan + plan_dir_path → guard passes (holistic allowed)."""
        FakeER = _make_fake_ensemble_reviewer_class()
        with (
            patch("millpy.reviewers.engine.project_root", return_value=tmp_path),
            patch("millpy.reviewers.engine.ClusterReviewer", FakeER),
        ):
            from millpy.reviewers.engine import run_reviewer
            prompt_file = tmp_path / "prompt.md"
            prompt_file.write_text("p\n", encoding="utf-8")
            result = run_reviewer(
                reviewer_name="g3flash-x3-sonnetmax",
                prompt_file=prompt_file,
                phase="plan",
                round=1,
                review_file_path=tmp_path / "out.md",
                plan_start_hash=None,
                plan_path=None,
                files_from=None,
                plan_dir_path=tmp_path / "plan",
            )
        assert result.verdict == "APPROVE"

    def test_tool_use_single_worker_passes_guard(self, tmp_path: Path):
        """Scenario 3: tool-use SingleWorker + plan + plan_dir_path → no ConfigError."""
        class FakeSW:
            def __init__(self, worker): self.worker = worker  # guard inspects .worker
            def run(self, **kw):
                kw["review_file_path"].write_text("VERDICT: APPROVE\n", encoding="utf-8")
                return ReviewerResult(
                    verdict="APPROVE",
                    review_file=kw["review_file_path"],
                    exit_code=0,
                    failure_kind=None,
                )

        with (
            patch("millpy.reviewers.engine.project_root", return_value=tmp_path),
            patch("millpy.reviewers.engine.SingleWorker", FakeSW),
        ):
            from millpy.reviewers.engine import run_reviewer
            prompt_file = tmp_path / "prompt.md"
            prompt_file.write_text("p\n", encoding="utf-8")
            result = run_reviewer(
                reviewer_name="sonnet",
                prompt_file=prompt_file,
                phase="plan",
                round=1,
                review_file_path=tmp_path / "out.md",
                plan_start_hash=None,
                plan_path=None,
                files_from=None,
                plan_dir_path=tmp_path / "plan",
            )
        assert result.verdict == "APPROVE"

    def test_bulk_without_plan_dir_passes_guard(self, tmp_path: Path):
        """Scenario 4: bulk SingleWorker + plan + plan_dir_path=None → no ConfigError."""
        class FakeSW:
            def __init__(self, worker): self.worker = worker  # guard inspects .worker
            def run(self, **kw):
                kw["review_file_path"].write_text("VERDICT: APPROVE\n", encoding="utf-8")
                return ReviewerResult(
                    verdict="APPROVE",
                    review_file=kw["review_file_path"],
                    exit_code=0,
                    failure_kind=None,
                )

        with (
            patch("millpy.reviewers.engine.project_root", return_value=tmp_path),
            patch("millpy.reviewers.engine.SingleWorker", FakeSW),
        ):
            from millpy.reviewers.engine import run_reviewer
            prompt_file = tmp_path / "prompt.md"
            prompt_file.write_text("p\n", encoding="utf-8")
            result = run_reviewer(
                reviewer_name="g3pro",
                prompt_file=prompt_file,
                phase="plan",
                round=1,
                review_file_path=tmp_path / "out.md",
                plan_start_hash=None,
                plan_path=None,
                files_from=None,
                plan_dir_path=None,
            )
        assert result.verdict == "APPROVE"
