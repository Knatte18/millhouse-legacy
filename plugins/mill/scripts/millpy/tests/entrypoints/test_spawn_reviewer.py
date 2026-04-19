"""Tests for millpy.entrypoints.spawn_reviewer — focused on the --list-reviewers flag.

Full dispatch contract tests are exercised by the reviewers/engine test suite
and by the integration tests in Step 14. This file covers the discovery flag
and the new error-message text that points at --list-reviewers.
"""
from __future__ import annotations


import pytest

from millpy.entrypoints import spawn_reviewer


def test_list_reviewers_exits_zero(capsys):
    exit_code = spawn_reviewer.main(["--list-reviewers"])
    assert exit_code == 0


def test_list_reviewers_prints_both_registries(capsys):
    spawn_reviewer.main(["--list-reviewers"])
    captured = capsys.readouterr()
    assert "WORKERS:" in captured.out
    assert "CLUSTERS:" in captured.out


def test_list_reviewers_lists_canonical_workers(capsys):
    spawn_reviewer.main(["--list-reviewers"])
    captured = capsys.readouterr()
    for worker_name in ("sonnet", "sonnetmax", "opus", "opusmax", "g3flash", "g3pro"):
        assert worker_name in captured.out


def test_list_reviewers_lists_ensembles(capsys):
    spawn_reviewer.main(["--list-reviewers"])
    captured = capsys.readouterr()
    assert "g3flash-x3-sonnetmax" in captured.out
    assert "g3pro-x2-opus" in captured.out


def test_list_reviewers_does_not_require_dispatch_args(capsys):
    """--list-reviewers alone must not trigger 'missing required argument' errors."""
    exit_code = spawn_reviewer.main(["--list-reviewers"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "missing required" not in captured.err.lower()


def test_dispatch_without_list_reviewers_requires_prompt_file(capsys):
    """When --list-reviewers is absent, --prompt-file / --phase / --round are required."""
    with pytest.raises(SystemExit):
        spawn_reviewer.main(["--phase", "plan", "--round", "1"])


def test_unknown_reviewer_name_error_mentions_list_flag(capsys, tmp_path, monkeypatch):
    """The config-resolution failure path mentions --list-reviewers in its error."""
    prompt = tmp_path / "prompt.md"
    prompt.write_text("hello\n", encoding="utf-8")
    monkeypatch.setattr(
        "millpy.core.paths.project_root",
        lambda **kwargs: tmp_path,
    )
    exit_code = spawn_reviewer.main([
        "--prompt-file", str(prompt),
        "--phase", "plan",
        "--round", "1",
    ])
    captured = capsys.readouterr()
    assert exit_code == 1
    combined = captured.out + captured.err
    assert "--list-reviewers" in combined


def test_reviewer_name_resolved_from_config_default(capsys, tmp_path, monkeypatch):
    """Reviewer name resolved from pipeline.<phase>-review.default when --reviewer-name absent."""
    import textwrap
    prompt = tmp_path / "prompt.md"
    prompt.write_text("hello\n", encoding="utf-8")
    config_dir = tmp_path / ".millhouse"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(
        textwrap.dedent("""\
            pipeline:
              plan-review:
                rounds: 3
                default: sonnetmax
        """),
        encoding="utf-8",
    )
    monkeypatch.setattr("millpy.core.paths.project_root", lambda **kwargs: tmp_path)

    captured_name: list[str] = []

    def fake_run_reviewer(*, reviewer_name, **kwargs):
        captured_name.append(reviewer_name)
        raise ValueError("fake-stop")

    monkeypatch.setattr("millpy.reviewers.engine.run_reviewer", fake_run_reviewer)
    spawn_reviewer.main([
        "--prompt-file", str(prompt),
        "--phase", "plan",
        "--round", "1",
    ])
    assert captured_name == ["sonnetmax"]


def test_explicit_reviewer_name_bypasses_config(capsys, tmp_path, monkeypatch):
    """--reviewer-name bypasses config resolution entirely."""
    import textwrap
    prompt = tmp_path / "prompt.md"
    prompt.write_text("hello\n", encoding="utf-8")
    config_dir = tmp_path / ".millhouse"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(
        textwrap.dedent("""\
            pipeline:
              plan-review:
                default: sonnetmax
        """),
        encoding="utf-8",
    )
    monkeypatch.setattr("millpy.core.paths.project_root", lambda **kwargs: tmp_path)

    captured_name: list[str] = []

    def fake_run_reviewer(*, reviewer_name, **kwargs):
        captured_name.append(reviewer_name)
        raise ValueError("fake-stop")

    monkeypatch.setattr("millpy.reviewers.engine.run_reviewer", fake_run_reviewer)
    spawn_reviewer.main([
        "--prompt-file", str(prompt),
        "--phase", "plan",
        "--round", "1",
        "--reviewer-name", "opus",
    ])
    assert captured_name == ["opus"]
