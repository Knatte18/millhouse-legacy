"""
test_handler.py — Unit tests for handler.synthesize FILES_PAYLOAD paths.

Three scenarios:
1. Tool-use handler + files_from → no <FILES_PAYLOAD> leftover (template has no placeholder)
2. Bulk handler + files_from valid → <FILES_PAYLOAD> replaced with inlined source files
3. Bulk handler + files_from=None → fallback text substituted
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch


from millpy.backends.base import BulkResult, ToolUseResult
from millpy.reviewers.base import Worker
from millpy.reviewers.handler import synthesize


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


def _make_fake_repo_root(tmp_path: Path, *, tool_use_template: str, bulk_template: str) -> Path:
    root = tmp_path / "repo"
    write_file(root / "plugins" / "mill" / "doc" / "prompts" / "handler.md", tool_use_template)
    write_file(root / "plugins" / "mill" / "doc" / "prompts" / "handler-bulk.md", bulk_template)
    return root


def _make_fake_tool_use_backend(output_path: Path):
    captured_prompts: list[str] = []

    def dispatch_tool_use(prompt, *, model, effort, max_turns):
        captured_prompts.append(prompt)
        output_path.write_text("VERDICT: APPROVE\n", encoding="utf-8")
        return ToolUseResult(
            result_text="VERDICT: APPROVE",
            parsed_json=None,
            exit_code=0,
            raw_stdout="VERDICT: APPROVE",
            raw_stderr="",
        )

    backend = MagicMock()
    backend.dispatch_tool_use = dispatch_tool_use
    return backend, captured_prompts


def _make_fake_bulk_backend(output_path: Path):
    captured_prompts: list[str] = []

    def dispatch_bulk(prompt, out_path, *, model, effort):
        captured_prompts.append(prompt)
        out_path.write_text("VERDICT: APPROVE\n", encoding="utf-8")
        return BulkResult(
            stdout="VERDICT: APPROVE",
            stderr="",
            exit_code=0,
            output_path=out_path,
        )

    backend = MagicMock()
    backend.dispatch_bulk = dispatch_bulk
    return backend, captured_prompts


# ---------------------------------------------------------------------------
# Scenario 1: Tool-use handler → no <FILES_PAYLOAD> leftover
# ---------------------------------------------------------------------------

class TestSynthesizeToolUseHandlerSkipsFilesPayload:
    def test_no_files_payload_leftover(self, tmp_path: Path):
        """Tool-use template has no <FILES_PAYLOAD>; files_from is silently ignored."""
        output_path = tmp_path / "out.md"
        root = _make_fake_repo_root(
            tmp_path,
            tool_use_template=(
                "Worker reports: <WORKER_REPORTS>\n"
                "Prep: <PREP_NOTES>\n"
                "Out: <OUTPUT_PATH>"
            ),
            bulk_template="Bulk: <WORKER_REPORTS>\nFiles: <FILES_PAYLOAD>\nOut: <OUTPUT_PATH>",
        )

        worker_report = write_file(tmp_path / "w1.md", "VERDICT: APPROVE\n")
        write_file(root / "src.py", "x = 1\n")
        files_from = write_file(tmp_path / "files.txt", "src.py\n")

        fake_backend, captured_prompts = _make_fake_tool_use_backend(output_path)

        with (
            patch("millpy.reviewers.handler.BACKENDS", {"claude": fake_backend}),
            patch("millpy.reviewers.handler.repo_root", return_value=root),
        ):
            synthesize(
                [worker_report],
                make_tool_use_worker(),
                output_path=output_path,
                files_from=files_from,
            )

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        assert "<FILES_PAYLOAD>" not in prompt
        assert "VERDICT: APPROVE" in prompt


# ---------------------------------------------------------------------------
# Scenario 2: Bulk handler + valid files_from → inlined source files
# ---------------------------------------------------------------------------

class TestSynthesizeBulkHandlerSubstitutesFilesPayload:
    def test_inlines_source_files_from_files_from(self, tmp_path: Path):
        """Bulk template has <FILES_PAYLOAD>; files_from entries are inlined."""
        output_path = tmp_path / "out.md"
        root = _make_fake_repo_root(
            tmp_path,
            tool_use_template="<WORKER_REPORTS><PREP_NOTES><OUTPUT_PATH>",
            bulk_template=(
                "Reports: <WORKER_REPORTS>\n"
                "Files: <FILES_PAYLOAD>\n"
                "Out: <OUTPUT_PATH>"
            ),
        )

        worker_report = write_file(tmp_path / "w1.md", "VERDICT: APPROVE\n")
        write_file(root / "src.py", "x = 1\n")
        files_from = write_file(tmp_path / "files.txt", "src.py\n")

        fake_backend, captured_prompts = _make_fake_bulk_backend(output_path)

        with (
            patch("millpy.reviewers.handler.BACKENDS", {"gemini": fake_backend}),
            patch("millpy.reviewers.handler.repo_root", return_value=root),
        ):
            synthesize(
                [worker_report],
                make_bulk_worker(),
                output_path=output_path,
                files_from=files_from,
            )

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        assert "<FILES_PAYLOAD>" not in prompt
        assert "src.py" in prompt
        assert "x = 1" in prompt


# ---------------------------------------------------------------------------
# Scenario 3: Bulk handler + files_from=None → fallback text
# ---------------------------------------------------------------------------

class TestSynthesizeBulkHandlerFilesFromNoneFallback:
    def test_uses_fallback_text_when_no_files_from(self, tmp_path: Path):
        """Bulk template has <FILES_PAYLOAD>; files_from=None → fallback text substituted."""
        output_path = tmp_path / "out.md"
        root = _make_fake_repo_root(
            tmp_path,
            tool_use_template="<WORKER_REPORTS><PREP_NOTES><OUTPUT_PATH>",
            bulk_template=(
                "Reports: <WORKER_REPORTS>\n"
                "Files: <FILES_PAYLOAD>\n"
                "Out: <OUTPUT_PATH>"
            ),
        )

        worker_report = write_file(tmp_path / "w1.md", "VERDICT: APPROVE\n")

        fake_backend, captured_prompts = _make_fake_bulk_backend(output_path)

        with (
            patch("millpy.reviewers.handler.BACKENDS", {"gemini": fake_backend}),
            patch("millpy.reviewers.handler.repo_root", return_value=root),
        ):
            synthesize(
                [worker_report],
                make_bulk_worker(),
                output_path=output_path,
                files_from=None,
            )

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        assert "(no source files provided — cannot independently verify worker claims)" in prompt
