"""
test_claude.py — Tests for millpy.backends.claude._parse_claude_json_wrapper
and ClaudeBackend.dispatch_tool_use_resume.

_parse_claude_json_wrapper returns tuple[dict, str | None] — (inner_dict, session_id).
dispatch_tool_use_resume unit tests mock subprocess_util.run.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from millpy.backends.claude import ClaudeBackend, _parse_claude_json_wrapper


def _wrap(result_value: object) -> str:
    """Build a minimal claude -p JSON wrapper string (no session_id)."""
    return json.dumps({"result": result_value, "cost": 0.01})


def _wrap_with_session(result_value: object, session_id: str) -> str:
    """Build a claude -p JSON wrapper string with a session_id field."""
    return json.dumps({"result": result_value, "cost": 0.01, "session_id": session_id})


class TestParsePlainWrapper:
    def test_plain_json_result(self):
        inner = json.dumps({"verdict": "APPROVE"})
        stdout = _wrap(inner)
        result, _ = _parse_claude_json_wrapper(stdout)
        assert result["verdict"] == "APPROVE"


class TestBacktickWrapping:
    def test_single_backtick_wrap(self):
        inner = json.dumps({"verdict": "APPROVE"})
        wrapped = f"`{inner}`"
        stdout = _wrap(wrapped)
        result, _ = _parse_claude_json_wrapper(stdout)
        assert result["verdict"] == "APPROVE"

    def test_triple_backtick_wrap_no_language(self):
        inner = json.dumps({"verdict": "APPROVE"})
        wrapped = f"```\n{inner}\n```"
        stdout = _wrap(wrapped)
        result, _ = _parse_claude_json_wrapper(stdout)
        assert result["verdict"] == "APPROVE"

    def test_triple_backtick_wrap_with_language_marker(self):
        inner = json.dumps({"verdict": "APPROVE"})
        wrapped = f"```json\n{inner}\n```"
        stdout = _wrap(wrapped)
        result, _ = _parse_claude_json_wrapper(stdout)
        assert result["verdict"] == "APPROVE"


class TestFallbackLineScan:
    def test_fallback_last_json_line(self):
        inner = json.dumps({"verdict": "APPROVE"})
        # Result is prose but stdout's last line is JSON
        prose = f"Here is some prose.\n{inner}"
        stdout = _wrap(prose)
        result, _ = _parse_claude_json_wrapper(stdout)
        assert result["verdict"] == "APPROVE"

    def test_fallback_json_embedded_in_prose(self):
        inner = json.dumps({"verdict": "REQUEST_CHANGES"})
        prose = f"Summary:\n{inner}\nEnd of review."
        # The last line isn't JSON, but there is one JSON line
        stdout = _wrap(prose)
        result, _ = _parse_claude_json_wrapper(stdout)
        assert result["verdict"] == "REQUEST_CHANGES"


class TestErrorCases:
    def test_empty_result_raises(self):
        stdout = _wrap("")
        with pytest.raises(ValueError, match="empty"):
            _parse_claude_json_wrapper(stdout)

    def test_whitespace_result_raises(self):
        stdout = _wrap("   ")
        with pytest.raises(ValueError, match="empty"):
            _parse_claude_json_wrapper(stdout)

    def test_null_result_raises(self):
        stdout = _wrap(None)
        with pytest.raises(ValueError, match="null"):
            _parse_claude_json_wrapper(stdout)

    def test_malformed_stdout_raises(self):
        with pytest.raises(ValueError, match="unparseable"):
            _parse_claude_json_wrapper("not json at all")


class TestEdgeCases:
    def test_utf8_nontascii_preserved(self):
        inner = json.dumps({"result": "naïveté", "verdict": "APPROVE"})
        stdout = _wrap(inner)
        result, _ = _parse_claude_json_wrapper(stdout)
        assert result["result"] == "naïveté"

    def test_unicode_in_wrapper(self):
        inner = json.dumps({"verdict": "APPROVE", "note": "café"})
        stdout = _wrap(inner)
        result, _ = _parse_claude_json_wrapper(stdout)
        assert result["note"] == "café"


class TestSessionIdExtraction:
    def test_session_id_present_extracted(self):
        inner = json.dumps({"verdict": "APPROVE"})
        stdout = _wrap_with_session(inner, session_id="abc-123-def")
        _, session_id = _parse_claude_json_wrapper(stdout)
        assert session_id == "abc-123-def"

    def test_session_id_absent_returns_none(self):
        inner = json.dumps({"verdict": "APPROVE"})
        stdout = _wrap(inner)  # no session_id field
        _, session_id = _parse_claude_json_wrapper(stdout)
        assert session_id is None

    def test_session_id_uuid_format(self):
        inner = json.dumps({"verdict": "APPROVE"})
        stdout = _wrap_with_session(inner, session_id="4c782baf-10ac-4e22-87ba-ae4b03d1344c")
        _, session_id = _parse_claude_json_wrapper(stdout)
        assert session_id == "4c782baf-10ac-4e22-87ba-ae4b03d1344c"

    def test_fallback_scan_session_id_is_none(self):
        # When stdout is not valid JSON (fallback path), session_id is None
        inner = json.dumps({"verdict": "APPROVE"})
        not_outer_json = f"not a wrapper\n{inner}"
        _, session_id = _parse_claude_json_wrapper(not_outer_json)
        assert session_id is None


# ---------------------------------------------------------------------------
# dispatch_tool_use_resume tests (mock subprocess)
# ---------------------------------------------------------------------------

def _make_completed_process(stdout: str, returncode: int = 0):
    """Build a mock CompletedProcess for subprocess_util.run."""
    mock = MagicMock()
    mock.returncode = returncode
    mock.stdout = stdout
    mock.stderr = ""
    return mock


# ---------------------------------------------------------------------------
# ToolUseResult.session_id field tests
# ---------------------------------------------------------------------------

class TestToolUseResultSessionId:
    def test_session_id_default_is_none(self):
        """ToolUseResult.session_id defaults to None for backward compat."""
        from millpy.backends.base import ToolUseResult

        result = ToolUseResult(
            result_text="",
            parsed_json=None,
            exit_code=0,
            raw_stdout="",
            raw_stderr="",
        )
        assert result.session_id is None

    def test_session_id_can_be_set(self):
        """ToolUseResult.session_id stores a string value."""
        from millpy.backends.base import ToolUseResult

        result = ToolUseResult(
            result_text="",
            parsed_json=None,
            exit_code=0,
            raw_stdout="",
            raw_stderr="",
            session_id="abc-123",
        )
        assert result.session_id == "abc-123"

    def test_session_id_is_immutable(self):
        """ToolUseResult is frozen — session_id cannot be mutated after construction."""
        from dataclasses import FrozenInstanceError
        from millpy.backends.base import ToolUseResult

        result = ToolUseResult(
            result_text="",
            parsed_json=None,
            exit_code=0,
            raw_stdout="",
            raw_stderr="",
            session_id="abc",
        )
        with pytest.raises(FrozenInstanceError):
            result.session_id = "new-value"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# dispatch_tool_use_resume tests (mock subprocess)
# ---------------------------------------------------------------------------

class TestDispatchToolUseResume:
    def _make_resume_stdout(self, result_text: str, session_id: str = "new-session-456") -> str:
        inner = json.dumps({"phase": "complete", "status_file": "/tmp/status.md", "final_commit": "abc123"})
        return json.dumps({"result": inner, "session_id": session_id, "cost": 0.01})

    def test_resume_calls_resume_flag(self):
        """dispatch_tool_use_resume must pass --resume <session_id> to the CLI."""
        backend = ClaudeBackend()
        stdout = self._make_resume_stdout("ok")
        with patch("millpy.backends.claude.subprocess_util.run") as mock_run:
            mock_run.return_value = _make_completed_process(stdout)
            backend.dispatch_tool_use_resume(
                "abc-123",
                "continue the work",
                model="sonnet",
                effort=None,
                max_turns=10,
            )
        argv = mock_run.call_args[0][0]
        assert "--resume" in argv
        assert "abc-123" in argv

    def test_resume_returns_tool_use_result(self):
        """dispatch_tool_use_resume returns a ToolUseResult."""
        from millpy.backends.base import ToolUseResult

        backend = ClaudeBackend()
        stdout = self._make_resume_stdout("ok", session_id="new-session-789")
        with patch("millpy.backends.claude.subprocess_util.run") as mock_run:
            mock_run.return_value = _make_completed_process(stdout)
            result = backend.dispatch_tool_use_resume(
                "old-session-123",
                "continue",
                model="sonnet",
                effort=None,
                max_turns=10,
            )
        assert isinstance(result, ToolUseResult)
        assert result.session_id == "new-session-789"
        assert result.exit_code == 0

    def test_resume_non_zero_exit(self):
        """Non-zero exit code from resume is surfaced in ToolUseResult."""
        backend = ClaudeBackend()
        with patch("millpy.backends.claude.subprocess_util.run") as mock_run:
            mock_run.return_value = _make_completed_process("", returncode=1)
            result = backend.dispatch_tool_use_resume(
                "bad-session",
                "continue",
                model="sonnet",
                effort=None,
                max_turns=10,
            )
        assert result.exit_code == 1
        assert result.parsed_json is None

    def test_resume_reuses_json_parsing(self):
        """dispatch_tool_use_resume parses JSON wrapper the same way as dispatch_tool_use."""
        backend = ClaudeBackend()
        inner = json.dumps({"verdict": "APPROVE"})
        stdout = json.dumps({"result": inner, "session_id": "s1", "cost": 0.01})
        with patch("millpy.backends.claude.subprocess_util.run") as mock_run:
            mock_run.return_value = _make_completed_process(stdout)
            result = backend.dispatch_tool_use_resume(
                "s0",
                "review this",
                model="sonnet",
                effort=None,
                max_turns=5,
            )
        assert result.parsed_json == {"verdict": "APPROVE"}
        assert result.session_id == "s1"


class TestSessionIdSurvivesFreeTextResult:
    """session_id must be captured even when inner result is free text (not JSON)."""

    def test_dispatch_tool_use_session_id_with_free_text_result(self):
        """When agent returns plain text (not JSON), session_id is still captured."""
        backend = ClaudeBackend()
        # Outer wrapper has session_id, but result is plain text
        stdout = json.dumps({
            "result": "Hello! I'm ready to help.",
            "session_id": "free-text-session-42",
            "cost": 0.01,
        })
        with patch("millpy.backends.claude.subprocess_util.run") as mock_run:
            mock_run.return_value = _make_completed_process(stdout)
            result = backend.dispatch_tool_use(
                "Say hello",
                model="sonnet",
                effort=None,
                max_turns=3,
            )
        assert result.session_id == "free-text-session-42"
        assert result.result_text == "Hello! I'm ready to help."
        assert result.exit_code == 0
        # parsed_json is None because inner result is not JSON
        assert result.parsed_json is None
