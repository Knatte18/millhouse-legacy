"""Tests for millpy.reviewers.failures — exit classification and malformed output."""
from __future__ import annotations

import pytest

from millpy.reviewers.failures import (
    KIND_BINARY_MISSING,
    KIND_BOT_GATE,
    KIND_MALFORMED,
    KIND_RATE_LIMIT,
    KIND_TIMEOUT,
    KIND_UNCLASSIFIED,
    WorkerFailure,
    classify_exit,
    is_malformed_output,
)


class TestClassifyExit:
    def test_rate_limit(self):
        assert classify_exit(10) == KIND_RATE_LIMIT

    def test_bot_gate(self):
        assert classify_exit(11) == KIND_BOT_GATE

    def test_binary_missing(self):
        assert classify_exit(12) == KIND_BINARY_MISSING

    def test_unclassified_13(self):
        assert classify_exit(13) == KIND_UNCLASSIFIED

    def test_success_returns_none(self):
        assert classify_exit(0) is None

    def test_other_nonzero_unclassified(self):
        assert classify_exit(1) == KIND_UNCLASSIFIED
        assert classify_exit(127) == KIND_UNCLASSIFIED
        assert classify_exit(-1) == KIND_UNCLASSIFIED


class TestIsMalformedOutput:
    def test_empty_is_malformed(self):
        assert is_malformed_output("") is True

    def test_random_text_is_malformed(self):
        assert is_malformed_output("some random text without VERDICT") is True

    def test_verdict_approve_not_malformed(self):
        assert is_malformed_output("VERDICT: APPROVE") is False

    def test_verdict_request_changes_not_malformed(self):
        assert is_malformed_output("VERDICT: REQUEST_CHANGES") is False

    def test_json_object_not_malformed(self):
        assert is_malformed_output('{"verdict": "APPROVE"}') is False

    def test_verdict_in_multiline_not_malformed(self):
        output = "Some review text\n\nVERDICT: REQUEST_CHANGES\n"
        assert is_malformed_output(output) is False

    def test_partial_json_is_malformed(self):
        assert is_malformed_output('{"incomplete": ') is True


class TestWorkerFailure:
    def test_dataclass_fields(self):
        wf = WorkerFailure(
            kind=KIND_BOT_GATE,
            detail="bot-gated",
            exit_code=11,
            stderr_tail="OAuth error",
        )
        assert wf.kind == KIND_BOT_GATE
        assert wf.detail == "bot-gated"
        assert wf.exit_code == 11
        assert wf.stderr_tail == "OAuth error"


class TestConstants:
    def test_kind_values(self):
        assert KIND_RATE_LIMIT == "rate-limit"
        assert KIND_BOT_GATE == "bot-gate"
        assert KIND_BINARY_MISSING == "binary-missing"
        assert KIND_UNCLASSIFIED == "unclassified"
        assert KIND_MALFORMED == "malformed-output"
        assert KIND_TIMEOUT == "timeout"
