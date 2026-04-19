"""Tests for millpy.reviewers.workers and clusters registries."""
from __future__ import annotations

from pathlib import Path

from millpy.reviewers.clusters import CLUSTERS
from millpy.reviewers.workers import WORKERS


def test_workers_invariants():
    for name, worker in WORKERS.items():
        assert worker.provider in {"claude", "gemini", "ollama"}, \
            f"{name}: unknown provider {worker.provider!r}"
        assert worker.dispatch_mode in {"tool-use", "bulk"}, \
            f"{name}: unknown dispatch_mode {worker.dispatch_mode!r}"
        if worker.provider != "claude":
            assert worker.effort is None, \
                f"{name}: effort must be None for non-claude provider, got {worker.effort!r}"


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


def test_clusters_invariants():
    for name, cluster in CLUSTERS.items():
        assert cluster.worker in WORKERS, \
            f"{name}: worker {cluster.worker!r} not in WORKERS"
        assert cluster.handler in WORKERS, \
            f"{name}: handler {cluster.handler!r} not in WORKERS"
        assert cluster.worker_count >= 1, \
            f"{name}: worker_count must be >= 1, got {cluster.worker_count}"
        assert isinstance(cluster.handler_prep, bool), \
            f"{name}: handler_prep must be bool, got {type(cluster.handler_prep).__name__}"
        if cluster.handler_prep:
            handler_dispatch = WORKERS[cluster.handler].dispatch_mode
            assert handler_dispatch == "tool-use", (
                f"{name}: handler_prep=True requires tool-use handler, "
                f"got {handler_dispatch!r}"
            )


def test_no_cross_import():
    import millpy.reviewers.workers as w_mod
    import millpy.reviewers.clusters as c_mod
    for mod_obj, bad in [
        (w_mod, "clusters"),
        (c_mod, "workers"),
    ]:
        mod_path = Path(mod_obj.__file__)
        lines = [ln for ln in mod_path.read_text(encoding="utf-8").splitlines() if ln.strip().startswith(("import ", "from "))]
        assert not any(bad in ln for ln in lines), f"{mod_path.name} must not import {bad}"
