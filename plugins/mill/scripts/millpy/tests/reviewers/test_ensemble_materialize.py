"""
test_ensemble_materialize.py — Tests for EnsembleReviewer._materialize_prompt
(five key scenarios from the plan requirements).
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from millpy.core.config import ConfigError
from millpy.reviewers.base import Worker
from millpy.reviewers.ensemble import _materialize_prompt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_tool_use_worker() -> Worker:
    return Worker(provider="claude", model="sonnet")


def make_bulk_worker() -> Worker:
    return Worker(provider="gemini", model="gemini-3-flash", dispatch_mode="bulk")


def write_file(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Scenario 1: Tool-use worker → prompt verbatim
# ---------------------------------------------------------------------------

class TestToolUseVerbatim:
    def test_tool_use_returns_prompt_verbatim(self, tmp_path):
        prompt_file = write_file(tmp_path / "prompt.md", "PROMPT CONTENT")
        worker = make_tool_use_worker()

        result = _materialize_prompt(
            prompt_file, "plan", worker, None,
            round=1,
            plan_overview=tmp_path / "overview.md",  # ignored for tool-use
            plan_batch=tmp_path / "batch.md",         # ignored
        )

        assert result == "PROMPT CONTENT"

    def test_tool_use_ignores_plan_overview_and_batch(self, tmp_path):
        prompt_file = write_file(tmp_path / "prompt.md", "VERBATIM")
        worker = make_tool_use_worker()
        # overview/batch don't even need to exist — tool-use ignores them
        result = _materialize_prompt(
            prompt_file, "plan", worker, None, round=1,
            plan_overview=Path("/nonexistent/overview.md"),
            plan_batch=Path("/nonexistent/batch.md"),
        )
        assert result == "VERBATIM"


# ---------------------------------------------------------------------------
# Scenario 2: Bulk per-batch mode
# ---------------------------------------------------------------------------

class TestBulkPerBatch:
    def _make_bulk_template(self, tmp_path: Path) -> Path:
        """Write a minimal plan-review-bulk.md template."""
        root = tmp_path / "repo"
        template_path = root / "plugins" / "mill" / "doc" / "prompts" / "plan-review-bulk.md"
        write_file(template_path, """\
            # Plan Review Bulk
            Round: <ROUND>
            Overview:
            <OVERVIEW_CONTENT>
            Batch:
            <BATCH_CONTENT>
            Constraints:
            <CONSTRAINTS_CONTENT>
            Files:
            <FILES_PAYLOAD>
        """)
        return root

    def test_bulk_per_batch_substitutes_tokens(self, tmp_path, monkeypatch):
        root = self._make_bulk_template(tmp_path)
        monkeypatch.chdir(root)

        # Patch repo_root to return our fake root
        import millpy.reviewers.ensemble as ens_mod
        monkeypatch.setattr(ens_mod, "repo_root", lambda: root)

        overview = write_file(root / "plan" / "00-overview.md", "OVERVIEW BODY")
        batch = write_file(root / "plan" / "01-core.md", "BATCH BODY")
        prompt_file = write_file(root / "prompt.md", "ignored for bulk per-batch")

        worker = make_bulk_worker()
        result = _materialize_prompt(
            prompt_file, "plan", worker, files_from=None,
            round=2,
            plan_overview=overview,
            plan_batch=batch,
        )

        assert "OVERVIEW BODY" in result
        assert "BATCH BODY" in result
        assert "Round: 2" in result

    def test_bulk_per_batch_raises_if_template_missing(self, tmp_path, monkeypatch):
        import millpy.reviewers.ensemble as ens_mod
        monkeypatch.setattr(ens_mod, "repo_root", lambda: tmp_path)

        overview = write_file(tmp_path / "overview.md", "ov")
        batch = write_file(tmp_path / "batch.md", "bt")
        prompt_file = write_file(tmp_path / "prompt.md", "x")

        worker = make_bulk_worker()
        with pytest.raises(ConfigError, match="plan-review-bulk.md"):
            _materialize_prompt(
                prompt_file, "plan", worker, None,
                plan_overview=overview, plan_batch=batch,
            )

    def test_bulk_per_batch_raises_if_overview_token_missing(self, tmp_path, monkeypatch):
        import millpy.reviewers.ensemble as ens_mod
        monkeypatch.setattr(ens_mod, "repo_root", lambda: tmp_path)

        template_path = tmp_path / "plugins" / "mill" / "doc" / "prompts" / "plan-review-bulk.md"
        write_file(template_path, "no tokens here, just <BATCH_CONTENT>")

        overview = write_file(tmp_path / "overview.md", "ov")
        batch = write_file(tmp_path / "batch.md", "bt")
        prompt_file = write_file(tmp_path / "prompt.md", "x")

        worker = make_bulk_worker()
        with pytest.raises(ConfigError, match="OVERVIEW_CONTENT"):
            _materialize_prompt(
                prompt_file, "plan", worker, None,
                plan_overview=overview, plan_batch=batch,
            )


# ---------------------------------------------------------------------------
# Scenario 3: Bulk + plan_dir_path → holistic mode (all plan files inlined)
# ---------------------------------------------------------------------------

def _write_holistic_template(root: Path) -> Path:
    template_path = root / "plugins" / "mill" / "doc" / "prompts" / "plan-review-bulk-holistic.md"
    write_file(
        template_path,
        "Plan: <PLAN_CONTENT>\nFiles: <FILES_PAYLOAD>\nConstraints: <CONSTRAINTS_CONTENT>\nRound: <ROUND>",
    )
    return template_path


class TestBulkHolisticMode:
    def test_materialize_holistic_bulk_substitutes_plan_content(self, tmp_path, monkeypatch):
        import millpy.reviewers.ensemble as ens_mod
        monkeypatch.setattr(ens_mod, "repo_root", lambda: tmp_path)
        _write_holistic_template(tmp_path)

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        write_file(plan_dir / "00-overview.md", "OVERVIEW BODY")
        write_file(plan_dir / "01-core.md", "BATCH BODY")

        prompt_file = write_file(tmp_path / "prompt.md", "x")
        worker = make_bulk_worker()

        result = _materialize_prompt(
            prompt_file, "plan", worker, None,
            round=1, plan_dir_path=plan_dir,
        )

        assert "=== 00-overview.md ===" in result
        assert "OVERVIEW BODY" in result
        assert "=== 01-core.md ===" in result
        assert "BATCH BODY" in result
        assert "Round: 1" in result

    def test_materialize_holistic_bulk_empty_dir_fallback(self, tmp_path, monkeypatch):
        import millpy.reviewers.ensemble as ens_mod
        monkeypatch.setattr(ens_mod, "repo_root", lambda: tmp_path)
        _write_holistic_template(tmp_path)

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        # empty dir

        prompt_file = write_file(tmp_path / "prompt.md", "x")
        worker = make_bulk_worker()

        result = _materialize_prompt(
            prompt_file, "plan", worker, None,
            plan_dir_path=plan_dir,
        )

        assert "(plan directory is empty)" in result

    def test_materialize_holistic_bulk_missing_template_raises_configerror(self, tmp_path, monkeypatch):
        import millpy.reviewers.ensemble as ens_mod
        monkeypatch.setattr(ens_mod, "repo_root", lambda: tmp_path)
        # intentionally do not create the template

        plan_dir = tmp_path / "plan"
        plan_dir.mkdir()
        write_file(plan_dir / "00-overview.md", "content")

        prompt_file = write_file(tmp_path / "prompt.md", "x")
        worker = make_bulk_worker()

        with pytest.raises(ConfigError, match="plan-review-bulk-holistic.md"):
            _materialize_prompt(
                prompt_file, "plan", worker, None,
                plan_dir_path=plan_dir,
            )


# ---------------------------------------------------------------------------
# Scenario 4: Bulk code-review v1 (existing behavior)
# ---------------------------------------------------------------------------

class TestBulkCodeReviewV1:
    def test_v1_plan_content_substituted(self, tmp_path, monkeypatch):
        import millpy.reviewers.ensemble as ens_mod
        monkeypatch.setattr(ens_mod, "repo_root", lambda: tmp_path)

        template_path = tmp_path / "plugins" / "mill" / "doc" / "prompts" / "code-review-bulk.md"
        write_file(template_path, "Plan: <PLAN_CONTENT>\nFiles: <FILES_PAYLOAD>\nRound: <ROUND>")

        plan_file = write_file(tmp_path / "_millhouse" / "task" / "plan.md", "---\nverify: noop\n---\n# Plan\n")
        files_from = write_file(tmp_path / "files.txt", "")

        prompt_file = write_file(tmp_path / "prompt.md", "x")
        worker = make_bulk_worker()

        result = _materialize_prompt(
            prompt_file, "code", worker, files_from,
            round=1, plan_path=plan_file,
        )

        assert "---\nverify: noop\n---\n# Plan\n" in result
        assert "Round: 1" in result


# ---------------------------------------------------------------------------
# Scenario 5: Bulk code-review v2 directory
# ---------------------------------------------------------------------------

class TestBulkCodeReviewV2:
    def test_v2_directory_uses_plan_io(self, tmp_path, monkeypatch):
        import millpy.reviewers.ensemble as ens_mod
        monkeypatch.setattr(ens_mod, "repo_root", lambda: tmp_path)

        template_path = tmp_path / "plugins" / "mill" / "doc" / "prompts" / "code-review-bulk.md"
        write_file(template_path, "Plan: <PLAN_CONTENT>\nFiles: <FILES_PAYLOAD>\nRound: <ROUND>")

        # Create a v2 plan directory
        task_dir = tmp_path / "_millhouse" / "task"
        plan_dir = task_dir / "plan"
        plan_dir.mkdir(parents=True)
        write_file(plan_dir / "00-overview.md", textwrap.dedent("""\
            ---
            kind: plan-overview
            task: T
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260101-000000
            batches: [core]
            ---
            # T
            ## Context
            x
            ## Shared Constraints
            x
            ## Shared Decisions
            x
            ## Batch Graph
            ```yaml
            batches:
              core:
                depends-on: []
                summary: "."
            ```
            ## All Files Touched
            - foo.py
        """))
        write_file(plan_dir / "01-core.md", "BATCH CONTENT")

        # plan_path points to the plan/ directory
        files_from = write_file(tmp_path / "files.txt", "")
        prompt_file = write_file(tmp_path / "prompt.md", "x")
        worker = make_bulk_worker()

        result = _materialize_prompt(
            prompt_file, "code", worker, files_from,
            round=1, plan_path=plan_dir,
        )

        # Should contain concatenated v2 content via plan_io
        assert "=== plan/00-overview.md ===" in result
        assert "BATCH CONTENT" in result
