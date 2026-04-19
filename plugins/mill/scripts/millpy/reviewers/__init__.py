"""
reviewers/__init__.py — Registry validation for millpy reviewer layer.

Imports WORKERS and CLUSTERS from their respective modules and validates
all invariants at import time. Any violation raises ValueError immediately
with a message naming the offending entry.

Validation invariants (per the import-time validation decision):
  1. Every Worker.provider is a key in BACKENDS.
  2. Worker.effort is None unless provider == "claude".
  3. Every Worker.dispatch_mode is in {"tool-use", "bulk"}.
  4. Every Cluster.worker and Cluster.handler is a valid WORKERS key.
  5. Every Cluster.worker_count >= 1 (also enforced by __post_init__).
  6. Name-space non-overlap: WORKERS.keys() & CLUSTERS.keys() == set().
"""
from __future__ import annotations

from millpy.backends import BACKENDS
from millpy.reviewers.base import Cluster, Worker
from millpy.reviewers.clusters import CLUSTERS
from millpy.reviewers.workers import WORKERS

__all__ = ["WORKERS", "CLUSTERS", "Worker", "Cluster", "validate_registries"]

_VALID_DISPATCH_MODES = {"tool-use", "bulk"}


def validate_registries() -> None:
    """Validate WORKERS and CLUSTERS registries.

    Raises
    ------
    ValueError
        If any invariant is violated, with a message naming the offending entry.
    """
    # Invariant 1: Every Worker.provider must be a key in BACKENDS.
    for name, worker in WORKERS.items():
        if worker.provider not in BACKENDS:
            raise ValueError(
                f"WORKERS[{name!r}]: unknown provider {worker.provider!r} — "
                f"not in BACKENDS {set(BACKENDS.keys())}"
            )

    # Invariant 2: Worker.effort must be None unless provider == "claude".
    for name, worker in WORKERS.items():
        if worker.effort is not None and worker.provider != "claude":
            raise ValueError(
                f"WORKERS[{name!r}]: effort={worker.effort!r} is only valid for "
                f"provider='claude'; provider={worker.provider!r}"
            )

    # Invariant 3: Every Worker.dispatch_mode in {"tool-use", "bulk"}.
    for name, worker in WORKERS.items():
        if worker.dispatch_mode not in _VALID_DISPATCH_MODES:
            raise ValueError(
                f"WORKERS[{name!r}]: dispatch_mode={worker.dispatch_mode!r} is not "
                f"in {_VALID_DISPATCH_MODES}"
            )

    # Invariant 4: Every Cluster.worker and Cluster.handler must be valid WORKERS keys.
    for name, ensemble in CLUSTERS.items():
        if ensemble.worker not in WORKERS:
            raise ValueError(
                f"CLUSTERS[{name!r}]: worker={ensemble.worker!r} is not a valid "
                f"WORKERS key"
            )
        if ensemble.handler not in WORKERS:
            raise ValueError(
                f"CLUSTERS[{name!r}]: handler={ensemble.handler!r} is not a valid "
                f"WORKERS key"
            )

    # Invariant 5: Every Cluster.worker_count >= 1.
    for name, ensemble in CLUSTERS.items():
        if ensemble.worker_count < 1:
            raise ValueError(
                f"CLUSTERS[{name!r}]: worker_count={ensemble.worker_count} must be >= 1"
            )

    # Invariant 6: Name-space non-overlap.
    overlap = set(WORKERS.keys()) & set(CLUSTERS.keys())
    if overlap:
        raise ValueError(
            f"Name(s) appear in both WORKERS and CLUSTERS: {overlap} — "
            "names must be unique across both registries"
        )


# Run validation at import time.
validate_registries()
