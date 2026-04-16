"""
test_base.py — Tests for millpy.backends.base Protocol shape and dataclasses.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from millpy.backends.base import Backend, BackendError, BulkResult, ToolUseResult


# ---------------------------------------------------------------------------
# BulkResult and ToolUseResult are frozen dataclasses
# ---------------------------------------------------------------------------

class TestBulkResult:
    def test_creation(self):
        r = BulkResult(
            stdout="output",
            stderr="err",
            exit_code=0,
            output_path=Path("/tmp/out.md"),
        )
        assert r.stdout == "output"
        assert r.exit_code == 0

    def test_frozen_raises_on_assignment(self):
        r = BulkResult(stdout="x", stderr="", exit_code=0, output_path=Path("/tmp/x"))
        with pytest.raises((AttributeError, TypeError)):
            r.stdout = "new"  # type: ignore[misc]


class TestToolUseResult:
    def test_creation(self):
        r = ToolUseResult(
            result_text="ok",
            parsed_json={"verdict": "APPROVE"},
            exit_code=0,
            raw_stdout="...",
            raw_stderr="",
        )
        assert r.parsed_json == {"verdict": "APPROVE"}

    def test_frozen_raises_on_assignment(self):
        r = ToolUseResult(
            result_text="ok",
            parsed_json=None,
            exit_code=0,
            raw_stdout="",
            raw_stderr="",
        )
        with pytest.raises((AttributeError, TypeError)):
            r.exit_code = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Backend Protocol runtime_checkable
# ---------------------------------------------------------------------------

class TestBackendProtocol:
    def test_stub_implementing_all_methods_passes_isinstance(self):
        class StubBackend:
            def dispatch_bulk(self, prompt, output_path, *, model, effort):
                pass

            def dispatch_tool_use(self, prompt, *, model, effort, max_turns):
                pass

            def dispatch_tool_use_resume(self, session_id, prompt, *, model, effort, max_turns):
                pass

        assert isinstance(StubBackend(), Backend)

    def test_stub_missing_dispatch_tool_use_fails_isinstance(self):
        class IncompleteBackend:
            def dispatch_bulk(self, prompt, output_path, *, model, effort):
                pass

        assert not isinstance(IncompleteBackend(), Backend)

    def test_stub_missing_dispatch_bulk_fails_isinstance(self):
        class IncompleteBackend:
            def dispatch_tool_use(self, prompt, *, model, effort, max_turns):
                pass

        assert not isinstance(IncompleteBackend(), Backend)


# ---------------------------------------------------------------------------
# BackendError
# ---------------------------------------------------------------------------

class TestBackendError:
    def test_is_exception(self):
        err = BackendError(kind="rate-limit", detail="too many requests")
        assert isinstance(err, Exception)

    def test_fields(self):
        err = BackendError(kind="bot-gate", detail="blocked")
        assert err.kind == "bot-gate"
        assert err.detail == "blocked"
