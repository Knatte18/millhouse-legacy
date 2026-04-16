"""Tests for millpy.reviewers.ensemble — EnsembleReviewer."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from millpy.backends.base import BulkResult, ToolUseResult
from millpy.core.config import ConfigError
from millpy.reviewers.base import Ensemble, ReviewerResult
from millpy.reviewers.ensemble import EnsembleReviewer, _materialize_prompt
from millpy.reviewers.workers import WORKERS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def prompt_file(tmp_path: Path) -> Path:
    f = tmp_path / "prompt.md"
    f.write_text("Review this code.\n", encoding="utf-8")
    return f


@pytest.fixture
def fake_review_file(tmp_path: Path) -> Path:
    return tmp_path / "review.md"


def _make_bulk_backend(output_text: str = "VERDICT: APPROVE\n", exit_code: int = 0):
    """Create a mock backend that returns a BulkResult."""
    backend = MagicMock()
    def dispatch_bulk(prompt, output_path, *, model, effort):
        output_path.write_text(output_text, encoding="utf-8")
        return BulkResult(
            stdout=output_text,
            stderr="",
            exit_code=exit_code,
            output_path=output_path,
        )
    backend.dispatch_bulk = dispatch_bulk
    return backend


def _make_tool_use_backend(result_text: str = "VERDICT: APPROVE\n", exit_code: int = 0):
    """Create a mock backend that returns a ToolUseResult."""
    backend = MagicMock()
    def dispatch_tool_use(prompt, *, model, effort, max_turns):
        return ToolUseResult(
            result_text=result_text,
            parsed_json=None,
            exit_code=exit_code,
            raw_stdout=result_text,
            raw_stderr="",
        )
    backend.dispatch_tool_use = dispatch_tool_use
    return backend


# ---------------------------------------------------------------------------
# Test: all workers fail → DEGRADED_FATAL
# ---------------------------------------------------------------------------

class TestEnsembleDegradation:
    def test_all_workers_fail_degraded_fatal(
        self, tmp_path: Path, prompt_file: Path, fake_review_file: Path
    ):
        """When all workers fail, return DEGRADED_FATAL."""
        failing_backend = MagicMock()
        failing_backend.dispatch_bulk.return_value = BulkResult(
            stdout="",
            stderr="OAuth error",
            exit_code=11,
            output_path=tmp_path / "w.md",
        )

        def dispatch_bulk_fail(prompt, output_path, *, model, effort):
            return BulkResult(
                stdout="",
                stderr="OAuth error",
                exit_code=11,
                output_path=output_path,
            )
        failing_backend.dispatch_bulk = dispatch_bulk_fail

        ensemble = Ensemble(worker="g3pro", worker_count=2, handler="opus")
        reviewer = EnsembleReviewer(ensemble)

        fake_root = tmp_path
        (fake_root / "_millhouse" / "scratch" / "reviews").mkdir(parents=True)

        synth_result = fake_review_file
        synth_result.write_text("VERDICT: APPROVE\n", encoding="utf-8")

        with (
            patch("millpy.reviewers.ensemble.BACKENDS", {
                "gemini": failing_backend,
                "claude": _make_tool_use_backend(),
            }),
            patch("millpy.reviewers.ensemble.repo_root", return_value=fake_root),
        ):
            result = reviewer.run(
                prompt_file=prompt_file,
                phase="code",
                round=1,
                review_file_path=fake_review_file,
                files_from=None,
            )

        assert result.verdict == "DEGRADED_FATAL"
        assert result.failure_kind is not None

    def test_one_worker_fails_survivors_synthesize(
        self, tmp_path: Path, prompt_file: Path, fake_review_file: Path
    ):
        """One failure + one success → synthesize from survivor."""
        call_count = [0]

        def dispatch_bulk_mixed(prompt, output_path, *, model, effort):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call fails
                return BulkResult(
                    stdout="",
                    stderr="error",
                    exit_code=11,
                    output_path=output_path,
                )
            # Second call succeeds
            output_path.write_text("VERDICT: APPROVE\n", encoding="utf-8")
            return BulkResult(
                stdout="VERDICT: APPROVE\n",
                stderr="",
                exit_code=0,
                output_path=output_path,
            )

        mixed_backend = MagicMock()
        mixed_backend.dispatch_bulk = dispatch_bulk_mixed

        tool_use_backend = _make_tool_use_backend("VERDICT: APPROVE\n")

        ensemble = Ensemble(worker="g3pro", worker_count=2, handler="opus")
        reviewer = EnsembleReviewer(ensemble)

        fake_root = tmp_path
        (fake_root / "_millhouse" / "scratch" / "reviews").mkdir(parents=True)
        fake_review_file.write_text("VERDICT: APPROVE\n", encoding="utf-8")

        def fake_synthesize(worker_results, handler_worker, output_path, prep_notes=None):
            output_path.write_text("VERDICT: APPROVE\n", encoding="utf-8")
            return output_path

        with (
            patch("millpy.reviewers.ensemble.BACKENDS", {
                "gemini": mixed_backend,
                "claude": tool_use_backend,
            }),
            patch("millpy.reviewers.ensemble.repo_root", return_value=fake_root),
            patch("millpy.reviewers.handler.synthesize", fake_synthesize),
        ):
            # Need to also patch the dynamic import
            import millpy.reviewers.handler as handler_mod
            with patch.object(handler_mod, "synthesize", fake_synthesize):
                result = reviewer.run(
                    prompt_file=prompt_file,
                    phase="code",
                    round=1,
                    review_file_path=fake_review_file,
                    files_from=None,
                )

        # Should not be DEGRADED_FATAL (at least one succeeded)
        assert result.verdict != "DEGRADED_FATAL"


# ---------------------------------------------------------------------------
# Test: bulk payload substitution
# ---------------------------------------------------------------------------

class TestBulkPayloadSubstitution:
    def test_bulk_template_missing_placeholder_raises(self, tmp_path: Path):
        """A bulk template missing <FILES_PAYLOAD> must raise ConfigError."""
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("No placeholder here.\n", encoding="utf-8")

        # Template without <FILES_PAYLOAD>
        prompts_dir = tmp_path / "plugins" / "mill" / "doc" / "prompts"
        prompts_dir.mkdir(parents=True)
        template = prompts_dir / "code-review-bulk.md"
        template.write_text("Review the files.\n", encoding="utf-8")

        files_from = tmp_path / "files.txt"
        files_from.write_text("", encoding="utf-8")

        worker = WORKERS["g3pro"]  # bulk dispatch

        with patch("millpy.reviewers.ensemble.repo_root", return_value=tmp_path):
            with pytest.raises(ConfigError, match="FILES_PAYLOAD"):
                _materialize_prompt(prompt_file, "code", worker, files_from)

    def test_bulk_payload_substituted(self, tmp_path: Path):
        """<FILES_PAYLOAD> placeholder is replaced with file contents."""
        # Create a source file to include
        src = tmp_path / "src.py"
        src.write_text("x = 1\n", encoding="utf-8")

        # Create files_from listing
        files_from = tmp_path / "files.txt"
        files_from.write_text("src.py\n", encoding="utf-8")

        # Create bulk template with placeholder
        prompts_dir = tmp_path / "plugins" / "mill" / "doc" / "prompts"
        prompts_dir.mkdir(parents=True)
        template = prompts_dir / "code-review-bulk.md"
        template.write_text("Review:\n<FILES_PAYLOAD>\n", encoding="utf-8")

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("plain prompt\n", encoding="utf-8")

        worker = WORKERS["g3pro"]

        with patch("millpy.reviewers.ensemble.repo_root", return_value=tmp_path):
            result = _materialize_prompt(prompt_file, "code", worker, files_from)

        assert "<FILES_PAYLOAD>" not in result
        assert "src.py" in result
        assert "x = 1" in result

    def test_no_files_from_uses_plain_prompt(self, tmp_path: Path):
        """When files_from is None, return plain prompt even for bulk worker."""
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("plain prompt\n", encoding="utf-8")

        worker = WORKERS["g3pro"]  # bulk dispatch

        result = _materialize_prompt(prompt_file, "code", worker, files_from=None)
        assert result == "plain prompt\n"

    def test_tool_use_worker_uses_plain_prompt(self, tmp_path: Path):
        """Tool-use workers always use the plain prompt regardless of files_from."""
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("plain prompt\n", encoding="utf-8")

        files_from = tmp_path / "files.txt"
        files_from.write_text("a.py\n", encoding="utf-8")

        worker = WORKERS["sonnet"]  # tool-use

        result = _materialize_prompt(prompt_file, "code", worker, files_from)
        assert result == "plain prompt\n"
