"""
test_claude.py — Tests for millpy.backends.claude._parse_claude_json_wrapper.

TDD applies ONLY to the pure helper _parse_claude_json_wrapper. The dispatch
methods are not unit-tested (covered by live smoke).
"""
from __future__ import annotations

import json

import pytest

from millpy.backends.claude import _parse_claude_json_wrapper


def _wrap(result_value: object) -> str:
    """Build a minimal claude -p JSON wrapper string."""
    return json.dumps({"result": result_value, "cost": 0.01})


class TestParsePlainWrapper:
    def test_plain_json_result(self):
        inner = json.dumps({"verdict": "APPROVE"})
        stdout = _wrap(inner)
        result = _parse_claude_json_wrapper(stdout)
        assert result["verdict"] == "APPROVE"


class TestBacktickWrapping:
    def test_single_backtick_wrap(self):
        inner = json.dumps({"verdict": "APPROVE"})
        wrapped = f"`{inner}`"
        stdout = _wrap(wrapped)
        result = _parse_claude_json_wrapper(stdout)
        assert result["verdict"] == "APPROVE"

    def test_triple_backtick_wrap_no_language(self):
        inner = json.dumps({"verdict": "APPROVE"})
        wrapped = f"```\n{inner}\n```"
        stdout = _wrap(wrapped)
        result = _parse_claude_json_wrapper(stdout)
        assert result["verdict"] == "APPROVE"

    def test_triple_backtick_wrap_with_language_marker(self):
        inner = json.dumps({"verdict": "APPROVE"})
        wrapped = f"```json\n{inner}\n```"
        stdout = _wrap(wrapped)
        result = _parse_claude_json_wrapper(stdout)
        assert result["verdict"] == "APPROVE"


class TestFallbackLineScan:
    def test_fallback_last_json_line(self):
        inner = json.dumps({"verdict": "APPROVE"})
        # Result is prose but stdout's last line is JSON
        prose = f"Here is some prose.\n{inner}"
        stdout = _wrap(prose)
        result = _parse_claude_json_wrapper(stdout)
        assert result["verdict"] == "APPROVE"

    def test_fallback_json_embedded_in_prose(self):
        inner = json.dumps({"verdict": "REQUEST_CHANGES"})
        prose = f"Summary:\n{inner}\nEnd of review."
        # The last line isn't JSON, but there is one JSON line
        stdout = _wrap(prose)
        result = _parse_claude_json_wrapper(stdout)
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
        result = _parse_claude_json_wrapper(stdout)
        assert result["result"] == "naïveté"

    def test_unicode_in_wrapper(self):
        inner = json.dumps({"verdict": "APPROVE", "note": "café"})
        stdout = _wrap(inner)
        result = _parse_claude_json_wrapper(stdout)
        assert result["note"] == "café"
