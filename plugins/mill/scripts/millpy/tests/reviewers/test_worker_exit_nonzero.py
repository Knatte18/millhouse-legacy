"""Regression tests — worker non-zero exit returns ERROR, not UNKNOWN.

Pins the contract at `reviewers/base.py:243-250` (SingleWorker.run). When the
backend subprocess exits non-zero and does NOT write the review file, the
`ReviewerResult` must have `verdict="ERROR"`, `exit_code != 0`, and
`failure_kind="worker_exit_nonzero"`. Never `"UNKNOWN"` — that verdict is
reserved for the verdict-extraction fallback when output text doesn't match
any recognized format.

Also covers the Ensemble path: a partial-failure ensemble (1 worker fails, 2
survive) still returns a synthesized verdict — the ensemble absorbs the
single worker's ERROR. Only when ALL workers fail does the ensemble return
`DEGRADED_FATAL`.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


from millpy.backends.base import BulkResult, ToolUseResult
from millpy.reviewers.base import ReviewerResult, SingleWorker, Worker


class _FakeBackend:
    """Minimal Backend-Protocol-compatible stub.

    Returns a fixed `ToolUseResult` / `BulkResult` from each dispatch call.
    The test supplies the exit code and output text.
    """

    def __init__(self, *, exit_code: int, output_text: str = ""):
        self._exit_code = exit_code
        self._output_text = output_text

    def dispatch_tool_use(self, prompt, *, model, effort, max_turns):
        return ToolUseResult(
            result_text=self._output_text,
            parsed_json=None,
            exit_code=self._exit_code,
            raw_stdout=self._output_text,
            raw_stderr="",
            session_id=None,
        )

    def dispatch_bulk(self, prompt, output_path, *, model, effort):
        return BulkResult(
            stdout=self._output_text,
            stderr="",
            exit_code=self._exit_code,
            output_path=output_path,
        )

    def dispatch_tool_use_resume(self, session_id, prompt, *, model, effort, max_turns):
        return self.dispatch_tool_use(prompt, model=model, effort=effort, max_turns=max_turns)


def _run_single_worker(tmp_path: Path, backend: _FakeBackend, *, dispatch_mode: str) -> ReviewerResult:
    """Spin up a SingleWorker with the fake backend mapped into BACKENDS."""
    worker = Worker(provider="claude", model="sonnet", dispatch_mode=dispatch_mode)
    sw = SingleWorker(worker=worker)

    prompt_file = tmp_path / "prompt.md"
    prompt_file.write_text("dummy prompt\n", encoding="utf-8")
    review_file = tmp_path / "review.md"

    with patch.dict("millpy.reviewers.base.BACKENDS", {"claude": backend}, clear=False):
        return sw.run(
            prompt_file=prompt_file,
            phase="code",
            round=1,
            review_file_path=review_file,
            files_from=None,
        )


class TestSingleWorkerExitNonzero:
    """Pin the verdict=ERROR contract for worker non-zero exits."""

    def test_tool_use_exit_1_returns_error_not_unknown(self, tmp_path):
        backend = _FakeBackend(exit_code=1)
        result = _run_single_worker(tmp_path, backend, dispatch_mode="tool-use")

        assert result.verdict == "ERROR"
        assert result.verdict != "UNKNOWN"  # belt-and-suspenders
        assert result.exit_code == 1
        assert result.failure_kind == "worker_exit_nonzero"

    def test_tool_use_exit_139_returns_error(self, tmp_path):
        """SIGSEGV-style exit (139) also returns ERROR, not UNKNOWN."""
        backend = _FakeBackend(exit_code=139)
        result = _run_single_worker(tmp_path, backend, dispatch_mode="tool-use")

        assert result.verdict == "ERROR"
        assert result.exit_code == 139
        assert result.failure_kind == "worker_exit_nonzero"

    def test_bulk_exit_1_returns_error(self, tmp_path):
        """Bulk dispatch path also returns ERROR on non-zero exit."""
        backend = _FakeBackend(exit_code=1)
        result = _run_single_worker(tmp_path, backend, dispatch_mode="bulk")

        assert result.verdict == "ERROR"
        assert result.exit_code == 1
        assert result.failure_kind == "worker_exit_nonzero"

    def test_exit_zero_with_approve_text_returns_approve(self, tmp_path):
        """Control: exit 0 with recognizable verdict text → APPROVE, not ERROR."""
        backend = _FakeBackend(exit_code=0, output_text="VERDICT: APPROVE\n")
        result = _run_single_worker(tmp_path, backend, dispatch_mode="tool-use")

        assert result.verdict == "APPROVE"
        assert result.exit_code == 0
        assert result.failure_kind is None

    def test_exit_zero_empty_output_returns_unknown_not_error(self, tmp_path):
        """Control: exit 0 with empty output → UNKNOWN (via verdict extraction).

        This is the ONE valid path to `UNKNOWN`: the process succeeded but
        produced no parseable verdict. Must NOT be confused with ERROR, which
        is reserved for worker exit failures.
        """
        backend = _FakeBackend(exit_code=0, output_text="")
        # Bulk mode writes output_text to review_file; tool-use doesn't. Use bulk
        # so the review file is written (tool-use would fail to find a file).
        result = _run_single_worker(tmp_path, backend, dispatch_mode="bulk")

        assert result.verdict == "UNKNOWN"
        assert result.exit_code == 0
        # NOT a worker-exit failure — exit was 0.
        assert result.failure_kind is None or result.failure_kind != "worker_exit_nonzero"


class TestEnsemblePartialFailure:
    """Document and pin ensemble behavior on per-worker failures.

    Observed behavior (see `reviewers/cluster.py:168-181`):
    - ALL workers fail → `verdict="DEGRADED_FATAL"`, `failure_kind` = first
      worker's failure kind, `exit_code=1`.
    - Some workers fail, some succeed → survivors' outputs are handed to the
      handler for synthesis. The single-worker ERROR is absorbed; the final
      verdict comes from the synthesized review.
    """

    def test_ensemble_absorbs_single_worker_failure_documented(self):
        """Marker test — pins expected behavior via code reference, not execution.

        A live ensemble spawn is heavy (ThreadPoolExecutor + handler synthesis).
        This regression pin keeps us from silently flipping the
        partial-failure-absorption semantics. See cluster.py:168-211.
        """
        from millpy.reviewers import cluster as ensemble_mod

        source = Path(ensemble_mod.__file__).read_text(encoding="utf-8")
        # If all workers fail → DEGRADED_FATAL (not ERROR).
        assert 'verdict="DEGRADED_FATAL"' in source or "verdict='DEGRADED_FATAL'" in source
        # Partial failure path continues to handler synthesis.
        assert "continuing with" in source  # log message when some survive
