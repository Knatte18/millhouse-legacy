"""Tests for millpy.reviewers.engine — run_reviewer with Fix E validation."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from millpy.core.config import ConfigError
from millpy.reviewers.base import ReviewerResult


def _fake_result(verdict: str = "APPROVE") -> ReviewerResult:
    return ReviewerResult(verdict=verdict, review_file=Path("/fake/review.md"), exit_code=0, failure_kind=None)


def _run(tmp_path: Path, reviewer_name: str, phase: str, review_file_path=None, mock_reviewer=None):
    """Helper to call run_reviewer with project_root patched to tmp_path."""
    from millpy.reviewers.engine import run_reviewer

    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("prompt\n", encoding="utf-8")
    patches = [patch("millpy.reviewers.engine.project_root", return_value=tmp_path)]
    if mock_reviewer is not None:
        patches.append(patch("millpy.reviewers.engine.SingleWorker", return_value=mock_reviewer))
    with patches[0]:
        ctx = patches[1] if len(patches) > 1 else None
        if ctx:
            with ctx:
                return run_reviewer(
                    reviewer_name=reviewer_name, prompt_file=prompt_file, phase=phase,
                    round=1, review_file_path=review_file_path, plan_start_hash=None,
                    plan_path=None, files_from=None,
                )
        return run_reviewer(
            reviewer_name=reviewer_name, prompt_file=prompt_file, phase=phase,
            round=1, review_file_path=review_file_path, plan_start_hash=None,
            plan_path=None, files_from=None,
        )


# ---------------------------------------------------------------------------
# Fix E — validate before mkdir
# ---------------------------------------------------------------------------

class TestFixE:
    def test_unknown_reviewer_raises_config_error(self, tmp_path: Path):
        with patch("millpy.reviewers.engine.project_root", return_value=tmp_path):
            with pytest.raises(ConfigError, match="unknown reviewer"):
                _run(tmp_path, "bogus-reviewer-xyz", "plan", tmp_path / "out.md")

    def test_unknown_reviewer_no_directory_created(self, tmp_path: Path):
        reviews_dir = tmp_path / "_millhouse" / "scratch" / "reviews"
        with patch("millpy.reviewers.engine.project_root", return_value=tmp_path):
            with pytest.raises(ConfigError):
                _run(tmp_path, "bogus-reviewer-xyz", "plan", tmp_path / "out.md")
        assert not reviews_dir.exists()

    def test_config_error_is_value_error_subclass(self):
        assert issubclass(ConfigError, ValueError)

    def test_bulk_in_discussion_raises_config_error(self, tmp_path: Path):
        reviews_dir = tmp_path / "_millhouse" / "scratch" / "reviews"
        with patch("millpy.reviewers.engine.project_root", return_value=tmp_path):
            with pytest.raises(ConfigError, match="discussion"):
                _run(tmp_path, "g3pro", "discussion", tmp_path / "out.md")
        assert not reviews_dir.exists()


# ---------------------------------------------------------------------------
# None path derivation
# ---------------------------------------------------------------------------

class TestNonePathDerivation:
    def test_none_path_is_derived(self, tmp_path: Path):
        mock_reviewer = MagicMock()

        def fake_run(*, prompt_file, phase, round, review_file_path, files_from, plan_path=None, plan_overview=None, plan_batch=None, plan_dir_path=None):
            review_file_path.write_text("VERDICT: APPROVE\n", encoding="utf-8")
            return ReviewerResult(verdict="APPROVE", review_file=review_file_path, exit_code=0, failure_kind=None)

        mock_reviewer.run = fake_run

        with (
            patch("millpy.reviewers.engine.project_root", return_value=tmp_path),
            patch("millpy.reviewers.engine.SingleWorker", return_value=mock_reviewer),
        ):
            from millpy.reviewers.engine import run_reviewer
            prompt_file = tmp_path / "prompt.md"
            prompt_file.write_text("prompt\n", encoding="utf-8")
            result = run_reviewer(
                reviewer_name="sonnet", prompt_file=prompt_file, phase="plan",
                round=1, review_file_path=None, plan_start_hash=None, plan_path=None, files_from=None,
            )

        assert result.review_file is not None
        assert "reviews" in str(result.review_file)
        assert result.review_file.exists()


# ---------------------------------------------------------------------------
# Resolution type (WORKERS→SingleWorker, REVIEWERS→EnsembleReviewer)
# ---------------------------------------------------------------------------

class TestResolutionType:
    def test_workers_entry_wraps_as_single_worker(self, tmp_path: Path):
        created = []

        class FakeSW:
            def __init__(self, worker): created.append("SW")
            def run(self, **kw):
                kw["review_file_path"].write_text("VERDICT: APPROVE\n", encoding="utf-8")
                return ReviewerResult(verdict="APPROVE", review_file=kw["review_file_path"], exit_code=0, failure_kind=None)

        from millpy.reviewers.engine import run_reviewer
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("p\n", encoding="utf-8")
        with (
            patch("millpy.reviewers.engine.project_root", return_value=tmp_path),
            patch("millpy.reviewers.engine.SingleWorker", FakeSW),
        ):
            run_reviewer(reviewer_name="sonnet", prompt_file=prompt_file, phase="plan",
                         round=1, review_file_path=tmp_path / "out.md",
                         plan_start_hash=None, plan_path=None, files_from=None)
        assert created == ["SW"]

    def test_reviewers_entry_wraps_as_ensemble(self, tmp_path: Path):
        created = []

        class FakeER:
            def __init__(self, ensemble): created.append("ER")
            def run(self, **kw):
                kw["review_file_path"].write_text("VERDICT: APPROVE\n", encoding="utf-8")
                return ReviewerResult(verdict="APPROVE", review_file=kw["review_file_path"], exit_code=0, failure_kind=None)

        from millpy.reviewers.engine import run_reviewer
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("p\n", encoding="utf-8")
        with (
            patch("millpy.reviewers.engine.project_root", return_value=tmp_path),
            patch("millpy.reviewers.engine.EnsembleReviewer", FakeER),
        ):
            run_reviewer(reviewer_name="g3pro-x2-opus", prompt_file=prompt_file,
                         phase="code", round=1, review_file_path=tmp_path / "out.md",
                         plan_start_hash=None, plan_path=None, files_from=None)
        assert created == ["ER"]
