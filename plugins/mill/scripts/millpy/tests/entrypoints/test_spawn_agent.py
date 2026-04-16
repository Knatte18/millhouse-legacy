"""Contract tests for millpy.entrypoints.spawn_agent.

Tests exercise spawn_agent at the Python level (main(argv) signature) rather
than as a subprocess. The contract matrix covers:

- Happy path: valid role+provider+prompt + fake backend output -> exit 0
- Missing required arg -> exit non-zero, stderr mentions the arg
- Missing provider AND no pipeline.implementer config -> exit non-zero
- Config fallback: pipeline.implementer from config.yaml when --provider absent
- Unknown provider -> exit 3
- Role-specific JSON validation (reviewer vs implementer)

The backends are monkeypatched at the Python level (BACKENDS dict) rather
than via a fake-claude binary on PATH. Step 14 adds the full fake-claude
binary fixture for cross-layout integration tests; these tests stay at the
unit level so they can run without a PATH fixture.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from millpy.entrypoints import spawn_agent


@dataclass
class _FakeToolUseResult:
    result_text: str
    parsed_json: dict | None
    exit_code: int
    raw_stdout: str
    raw_stderr: str = ""
    session_id: str | None = None


@dataclass
class _FakeBulkResult:
    stdout: str
    stderr: str
    exit_code: int
    output_path: Path


class _FakeClaudeBackend:
    """Fake backend that returns a canned ToolUseResult from an attribute."""

    def __init__(self, canned: _FakeToolUseResult | None = None):
        self.canned = canned or _FakeToolUseResult(
            result_text='{"verdict": "APPROVE", "review_file": "/tmp/x.md"}',
            parsed_json={"verdict": "APPROVE", "review_file": "/tmp/x.md"},
            exit_code=0,
            raw_stdout='{"result": "{\\"verdict\\": \\"APPROVE\\", \\"review_file\\": \\"/tmp/x.md\\"}"}',
        )
        self.dispatch_calls: list[dict] = []
        self.resume_calls: list[dict] = []

    def dispatch_tool_use(self, prompt, *, model, effort, max_turns):
        self.dispatch_calls.append({
            "prompt": prompt,
            "model": model,
            "effort": effort,
            "max_turns": max_turns,
        })
        return self.canned

    def dispatch_tool_use_resume(self, session_id, prompt, *, model, effort, max_turns):
        self.resume_calls.append({
            "session_id": session_id,
            "prompt": prompt,
            "model": model,
            "effort": effort,
            "max_turns": max_turns,
        })
        return self.canned

    def dispatch_bulk(self, prompt, output_path, *, model, effort):
        self.dispatch_calls.append({
            "prompt": prompt,
            "model": model,
            "effort": effort,
            "output_path": output_path,
        })
        output_path.write_text(self.canned.result_text, encoding="utf-8")
        return _FakeBulkResult(
            stdout=self.canned.result_text,
            stderr="",
            exit_code=0,
            output_path=output_path,
        )


@pytest.fixture
def prompt_file(tmp_path):
    path = tmp_path / "prompt.md"
    path.write_text("test prompt\n", encoding="utf-8")
    return path


@pytest.fixture
def fake_backend(monkeypatch):
    from millpy.backends import BACKENDS
    backend = _FakeClaudeBackend()
    monkeypatch.setitem(BACKENDS, "claude", backend)
    return backend


def test_happy_path_reviewer(fake_backend, prompt_file, capsys):
    exit_code = spawn_agent.main([
        "--role", "reviewer",
        "--prompt-file", str(prompt_file),
        "--provider", "sonnet",
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())
    assert parsed == {"verdict": "APPROVE", "review_file": "/tmp/x.md"}
    assert fake_backend.dispatch_calls[0]["model"] == "sonnet"


def test_happy_path_implementer(fake_backend, prompt_file, capsys):
    fake_backend.canned = _FakeToolUseResult(
        result_text='{"phase": "complete", "status_file": "_millhouse/task/status.md", "final_commit": "abc123"}',
        parsed_json={"phase": "complete", "status_file": "_millhouse/task/status.md", "final_commit": "abc123"},
        exit_code=0,
        raw_stdout="",
    )
    exit_code = spawn_agent.main([
        "--role", "implementer",
        "--prompt-file", str(prompt_file),
        "--provider", "sonnet",
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())
    assert parsed["phase"] == "complete"
    assert parsed["final_commit"] == "abc123"


def test_missing_role_exits_nonzero(prompt_file, capsys):
    with pytest.raises(SystemExit) as exc_info:
        spawn_agent.main(["--prompt-file", str(prompt_file), "--provider", "sonnet"])
    assert exc_info.value.code != 0


def test_missing_prompt_file_arg_exits_nonzero(capsys):
    with pytest.raises(SystemExit) as exc_info:
        spawn_agent.main(["--role", "reviewer", "--provider", "sonnet"])
    assert exc_info.value.code != 0


def test_prompt_file_not_on_disk_exits_1(capsys):
    exit_code = spawn_agent.main([
        "--role", "reviewer",
        "--prompt-file", "/nonexistent/prompt.md",
        "--provider", "sonnet",
    ])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "prompt file" in captured.err.lower() or "not found" in captured.err.lower()


def test_unknown_provider_exits_3(prompt_file, capsys):
    exit_code = spawn_agent.main([
        "--role", "reviewer",
        "--prompt-file", str(prompt_file),
        "--provider", "nonsense_model_name",
    ])
    assert exit_code == 3
    captured = capsys.readouterr()
    assert "not implemented" in captured.err.lower() or "unknown" in captured.err.lower()


def test_missing_provider_and_no_config_exits_1(prompt_file, monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "millpy.core.paths.project_root",
        lambda **kwargs: tmp_path,
    )
    exit_code = spawn_agent.main([
        "--role", "reviewer",
        "--prompt-file", str(prompt_file),
    ])
    assert exit_code == 1
    captured = capsys.readouterr()
    err = captured.err.lower()
    assert "--provider" in err or "pipeline.implementer" in err


def test_config_fallback_reads_pipeline_implementer(
    fake_backend, prompt_file, monkeypatch, tmp_path, capsys
):
    millhouse = tmp_path / "_millhouse"
    millhouse.mkdir()
    (millhouse / "config.yaml").write_text(
        "pipeline:\n  implementer: sonnet\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "millpy.core.paths.project_root",
        lambda **kwargs: tmp_path,
    )

    exit_code = spawn_agent.main([
        "--role", "reviewer",
        "--prompt-file", str(prompt_file),
    ])
    assert exit_code == 0
    assert fake_backend.dispatch_calls[0]["model"] == "sonnet"


def test_reviewer_missing_verdict_field_exits_1(fake_backend, prompt_file, capsys):
    fake_backend.canned = _FakeToolUseResult(
        result_text='{"wrong_field": "APPROVE"}',
        parsed_json={"wrong_field": "APPROVE"},
        exit_code=0,
        raw_stdout="",
    )
    exit_code = spawn_agent.main([
        "--role", "reviewer",
        "--prompt-file", str(prompt_file),
        "--provider", "sonnet",
    ])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "verdict" in captured.err.lower()


def test_implementer_missing_phase_field_exits_1(fake_backend, prompt_file, capsys):
    fake_backend.canned = _FakeToolUseResult(
        result_text='{"final_commit": "abc"}',
        parsed_json={"final_commit": "abc"},
        exit_code=0,
        raw_stdout="",
    )
    exit_code = spawn_agent.main([
        "--role", "implementer",
        "--prompt-file", str(prompt_file),
        "--provider", "sonnet",
    ])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "phase" in captured.err.lower()


def test_backend_nonzero_exit_propagates(fake_backend, prompt_file, capsys):
    fake_backend.canned = _FakeToolUseResult(
        result_text="",
        parsed_json=None,
        exit_code=42,
        raw_stdout="",
        raw_stderr="[claude] something broke",
    )
    exit_code = spawn_agent.main([
        "--role", "reviewer",
        "--prompt-file", str(prompt_file),
        "--provider", "sonnet",
    ])
    assert exit_code == 1


def test_max_turns_default_reviewer_is_20(fake_backend, prompt_file):
    spawn_agent.main([
        "--role", "reviewer",
        "--prompt-file", str(prompt_file),
        "--provider", "sonnet",
    ])
    assert fake_backend.dispatch_calls[0]["max_turns"] == 20


def test_max_turns_default_implementer_is_200(fake_backend, prompt_file):
    fake_backend.canned = _FakeToolUseResult(
        result_text='{"phase": "complete", "status_file": "s", "final_commit": "c"}',
        parsed_json={"phase": "complete", "status_file": "s", "final_commit": "c"},
        exit_code=0,
        raw_stdout="",
    )
    spawn_agent.main([
        "--role", "implementer",
        "--prompt-file", str(prompt_file),
        "--provider", "sonnet",
    ])
    assert fake_backend.dispatch_calls[0]["max_turns"] == 200


def test_max_turns_override(fake_backend, prompt_file):
    spawn_agent.main([
        "--role", "reviewer",
        "--prompt-file", str(prompt_file),
        "--provider", "sonnet",
        "--max-turns", "5",
    ])
    assert fake_backend.dispatch_calls[0]["max_turns"] == 5


def test_effort_flag_passed_to_backend(fake_backend, prompt_file):
    spawn_agent.main([
        "--role", "reviewer",
        "--prompt-file", str(prompt_file),
        "--provider", "sonnetmax",
    ])
    assert fake_backend.dispatch_calls[0]["effort"] == "max"


def test_worker_by_registry_name_resolves_model(fake_backend, prompt_file):
    spawn_agent.main([
        "--role", "reviewer",
        "--prompt-file", str(prompt_file),
        "--provider", "opus",
    ])
    assert fake_backend.dispatch_calls[0]["model"] == "opus"


def test_unicode_prompt_round_trips(fake_backend, tmp_path):
    prompt_file = tmp_path / "unicode.md"
    prompt_file.write_text("Norsk: æøå, emoji: ✨, CJK: 日本語\n", encoding="utf-8")
    exit_code = spawn_agent.main([
        "--role", "reviewer",
        "--prompt-file", str(prompt_file),
        "--provider", "sonnet",
    ])
    assert exit_code == 0
    dispatched_prompt = fake_backend.dispatch_calls[0]["prompt"]
    assert "æøå" in dispatched_prompt
    assert "✨" in dispatched_prompt
    assert "日本語" in dispatched_prompt


# ---------------------------------------------------------------------------
# --session-id tests (Step 15)
# ---------------------------------------------------------------------------

def test_implementer_output_includes_session_id(fake_backend, prompt_file, capsys):
    """First spawn without --session-id → implementer output includes session_id."""
    fake_backend.canned = _FakeToolUseResult(
        result_text='{"phase": "complete", "status_file": "s.md", "final_commit": "abc"}',
        parsed_json={"phase": "complete", "status_file": "s.md", "final_commit": "abc"},
        exit_code=0,
        raw_stdout="",
        session_id="captured-session-111",
    )
    exit_code = spawn_agent.main([
        "--role", "implementer",
        "--prompt-file", str(prompt_file),
        "--provider", "sonnet",
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())
    assert parsed["session_id"] == "captured-session-111"


def test_resume_uses_dispatch_tool_use_resume(fake_backend, prompt_file, capsys):
    """--session-id flag → uses dispatch_tool_use_resume instead of dispatch_tool_use."""
    fake_backend.canned = _FakeToolUseResult(
        result_text='{"phase": "complete", "status_file": "s.md", "final_commit": "def"}',
        parsed_json={"phase": "complete", "status_file": "s.md", "final_commit": "def"},
        exit_code=0,
        raw_stdout="",
        session_id="resumed-session-222",
    )
    exit_code = spawn_agent.main([
        "--role", "implementer",
        "--prompt-file", str(prompt_file),
        "--provider", "sonnet",
        "--session-id", "prev-session-111",
    ])
    assert exit_code == 0
    # dispatch_tool_use should NOT have been called
    assert len(fake_backend.dispatch_calls) == 0
    # dispatch_tool_use_resume should have been called with the session_id
    assert len(fake_backend.resume_calls) == 1
    assert fake_backend.resume_calls[0]["session_id"] == "prev-session-111"
    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())
    assert parsed["session_id"] == "resumed-session-222"


def test_session_id_with_bulk_dispatch_exits_1(fake_backend, prompt_file, tmp_path, capsys):
    """--session-id with --dispatch bulk → error, exit 1."""
    bulk_out = tmp_path / "out.md"
    exit_code = spawn_agent.main([
        "--role", "reviewer",
        "--prompt-file", str(prompt_file),
        "--provider", "sonnet",
        "--dispatch", "bulk",
        "--bulk-output", str(bulk_out),
        "--session-id", "some-session",
    ])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "bulk" in captured.err.lower() or "session" in captured.err.lower()


def test_implementer_session_id_none_when_absent(fake_backend, prompt_file, capsys):
    """session_id field is None in output when backend returns no session_id."""
    fake_backend.canned = _FakeToolUseResult(
        result_text='{"phase": "complete", "status_file": "s.md", "final_commit": "xyz"}',
        parsed_json={"phase": "complete", "status_file": "s.md", "final_commit": "xyz"},
        exit_code=0,
        raw_stdout="",
        session_id=None,
    )
    exit_code = spawn_agent.main([
        "--role", "implementer",
        "--prompt-file", str(prompt_file),
        "--provider", "sonnet",
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip())
    assert "session_id" in parsed
    assert parsed["session_id"] is None
