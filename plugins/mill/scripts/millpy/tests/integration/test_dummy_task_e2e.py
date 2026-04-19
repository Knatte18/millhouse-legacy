"""
test_dummy_task_e2e.py — End-to-end smoke test (D.3).

The full skill chain (mill-setup -> mill-spawn -> mill-start -> mill-go
-> mill-merge) cannot run inside pytest because mill-start and mill-go
are interactive Claude Code skills. Instead, this smoke exercises the
SUBPROCESS chain that sits under every skill — spawn_agent and
spawn_reviewer — against the fake-claude binary fixture from Step 14.

This is the test that would have caught the verdict-UNKNOWN bug the
live discussion-review reproduced twice in this worktree: the fake
returns a fence-wrapped JSON response, spawn_agent must unwrap it via
millpy.core.verdict.parse_verdict_line, and the caller receives a clean
verdict envelope.

Zero-PS1 assertion: D.6's subprocess_logging emits `[millpy.*] spawning: <cmd>`
lines to stderr on every subprocess.run call. The test captures stderr
and asserts no `.ps1` substring appears. This is the behavioral gate
that proves no PS1 script is called anywhere in the chain.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


FIXTURES_BIN = (
    Path(__file__).resolve().parent.parent / "fixtures" / "bin"
)
# test file lives at plugins/mill/scripts/millpy/tests/integration/test_dummy_task_e2e.py
# parents[0]=integration  parents[1]=tests  parents[2]=millpy
# parents[3]=scripts  parents[4]=mill  parents[5]=plugins  parents[6]=repo root
REPO_ROOT = Path(__file__).resolve().parents[6]
SCRIPTS_DIR = REPO_ROOT / "plugins" / "mill" / "scripts"


@pytest.fixture
def fake_claude_path(monkeypatch):
    """Prepend fixtures/bin to PATH so spawn_agent resolves the fake as `claude`.

    On Windows, CreateProcess uses the parent process's PATH from os.environ
    (not the `env=` argument of subprocess.run), so this fixture uses
    monkeypatch.setenv to set os.environ["PATH"] for the test's process —
    which becomes the parent's PATH when spawn_agent itself spawns claude.
    """
    current_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", str(FIXTURES_BIN) + os.pathsep + current_path)
    return FIXTURES_BIN


def _run_spawn_agent(prompt_file: Path, args: list[str], response: str, exit_code: str = "0") -> subprocess.CompletedProcess:
    """Invoke millpy.entrypoints.spawn_agent as a subprocess with the fake-claude response set."""
    env = dict(os.environ)
    env["MILL_FAKE_CLAUDE_RESPONSE"] = response
    env["MILL_FAKE_CLAUDE_EXIT_CODE"] = exit_code
    env["PYTHONIOENCODING"] = "utf-8"

    return subprocess.run(
        [
            sys.executable,
            "-m", "millpy.entrypoints.spawn_agent",
            "--prompt-file", str(prompt_file),
            *args,
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        cwd=str(SCRIPTS_DIR),
    )


def test_spawn_agent_reviewer_roundtrip_via_fake_claude(tmp_path, fake_claude_path):
    """spawn_agent.py end-to-end with a fake-claude on PATH, reviewer role."""
    prompt = tmp_path / "prompt.md"
    prompt.write_text("test prompt\n", encoding="utf-8")

    result = _run_spawn_agent(
        prompt,
        ["--role", "reviewer", "--provider", "sonnet", "--max-turns", "1"],
        response='{"verdict": "APPROVE", "review_file": "/tmp/fake.md"}',
    )

    assert result.returncode == 0, (
        f"spawn_agent exited {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    parsed = json.loads(result.stdout.strip())
    assert parsed["verdict"] == "APPROVE"
    assert parsed["review_file"] == "/tmp/fake.md"

    assert ".ps1" not in result.stderr, (
        f"PS1 spawn detected in captured stderr — must be zero. stderr:\n{result.stderr}"
    )


def test_spawn_agent_reviewer_handles_fence_wrapped_response(tmp_path, fake_claude_path):
    """Fence-wrapped JSON from the fake must round-trip through parse_verdict_line."""
    prompt = tmp_path / "prompt.md"
    prompt.write_text("test prompt\n", encoding="utf-8")

    result = _run_spawn_agent(
        prompt,
        ["--role", "reviewer", "--provider", "sonnet", "--max-turns", "1"],
        response='`{"verdict": "GAPS_FOUND", "review_file": "/tmp/wrapped.md"}`',
    )

    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout.strip())
    assert parsed["verdict"] == "GAPS_FOUND"


def test_spawn_agent_implementer_role_validation(tmp_path, fake_claude_path):
    """Implementer-role canned response must have phase/status_file/final_commit."""
    prompt = tmp_path / "prompt.md"
    prompt.write_text("test prompt\n", encoding="utf-8")

    result = _run_spawn_agent(
        prompt,
        ["--role", "implementer", "--provider", "sonnet", "--max-turns", "1"],
        response=(
            '{"phase": "complete", "status_file": ".millhouse/task/status.md", '
            '"final_commit": "abc123"}'
        ),
    )

    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout.strip())
    assert parsed["phase"] == "complete"
    assert parsed["final_commit"] == "abc123"


def test_spawn_agent_nonzero_fake_claude_propagates(tmp_path, fake_claude_path):
    """When the fake exits non-zero, spawn_agent propagates a non-zero exit."""
    prompt = tmp_path / "prompt.md"
    prompt.write_text("test prompt\n", encoding="utf-8")

    result = _run_spawn_agent(
        prompt,
        ["--role", "reviewer", "--provider", "sonnet", "--max-turns", "1"],
        response='{"verdict": "APPROVE", "review_file": "/tmp/x.md"}',
        exit_code="1",
    )

    assert result.returncode != 0
