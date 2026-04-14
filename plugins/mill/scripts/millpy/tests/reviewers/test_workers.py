"""Tests for millpy.reviewers.workers and definitions registries."""
from __future__ import annotations

from millpy.reviewers.definitions import REVIEWERS
from millpy.reviewers.workers import WORKERS


def test_workers_count_and_no_haiku():
    assert len(WORKERS) == 8
    assert "haiku" not in WORKERS


def test_workers_dispatch_modes():
    for name in ("sonnet", "sonnetmax", "opus", "opusmax", "glmflash", "qwenthinker"):
        assert WORKERS[name].dispatch_mode == "tool-use", name
    for name in ("gemini3pro", "gemini3flash"):
        assert WORKERS[name].dispatch_mode == "bulk", name


def test_workers_effort_and_extras():
    assert WORKERS["sonnetmax"].effort == "max"
    assert WORKERS["opusmax"].effort == "max"
    assert WORKERS["sonnet"].effort is None
    assert WORKERS["qwenthinker"].extras == {"think": True}


def test_reviewers_count_and_keys():
    assert len(REVIEWERS) == 3
    assert "ensemble-gemini3pro-x2-opus" in REVIEWERS
    assert REVIEWERS["ensemble-gemini3pro-x2-opus"].worker_count == 2
    assert REVIEWERS["ensemble-gemini3pro-x2-opus"].handler == "opus"


def test_no_cross_import():
    for mod, bad in [
        ("plugins/mill/scripts/millpy/reviewers/workers.py", "definitions"),
        ("plugins/mill/scripts/millpy/reviewers/definitions.py", "workers"),
    ]:
        lines = [l for l in open(mod, encoding="utf-8") if l.strip().startswith(("import ", "from "))]
        assert not any(bad in l for l in lines), f"{mod} must not import {bad}"
