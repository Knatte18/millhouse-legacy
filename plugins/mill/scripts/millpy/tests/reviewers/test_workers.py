"""Tests for millpy.reviewers.workers and definitions registries."""
from __future__ import annotations

from pathlib import Path

from millpy.reviewers.definitions import REVIEWERS
from millpy.reviewers.workers import WORKERS


def test_workers_core_names_present():
    for name in ("sonnet", "sonnetmax", "opus", "opusmax", "glmflash",
                 "qwenthinker", "g3pro", "g3flash"):
        assert name in WORKERS, name


def test_workers_dispatch_modes():
    for name in ("sonnet", "sonnetmax", "opus", "opusmax", "glmflash", "qwenthinker"):
        assert WORKERS[name].dispatch_mode == "tool-use", name
    for name in ("g3pro", "g3flash"):
        assert WORKERS[name].dispatch_mode == "bulk", name


def test_workers_effort_and_extras():
    assert WORKERS["sonnetmax"].effort == "max"
    assert WORKERS["opusmax"].effort == "max"
    assert WORKERS["sonnet"].effort is None
    assert WORKERS["qwenthinker"].extras == {"think": True}


def test_reviewers_core_keys_present():
    assert "g3pro-x2-opus" in REVIEWERS
    assert REVIEWERS["g3pro-x2-opus"].worker_count == 2
    assert REVIEWERS["g3pro-x2-opus"].handler == "opus"
    assert "g3flash-x3-sonnetmax" in REVIEWERS
    assert REVIEWERS["g3flash-x3-sonnetmax"].worker == "g3flash"
    assert REVIEWERS["g3flash-x3-sonnetmax"].worker_count == 3
    assert REVIEWERS["g3flash-x3-sonnetmax"].handler == "sonnetmax"


def test_no_cross_import():
    import millpy.reviewers.workers as w_mod
    import millpy.reviewers.definitions as d_mod
    for mod_obj, bad in [
        (w_mod, "definitions"),
        (d_mod, "workers"),
    ]:
        mod_path = Path(mod_obj.__file__)
        lines = [l for l in mod_path.read_text(encoding="utf-8").splitlines() if l.strip().startswith(("import ", "from "))]
        assert not any(bad in l for l in lines), f"{mod_path.name} must not import {bad}"
