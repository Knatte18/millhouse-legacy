"""
reviewers/__init__.py — Registry validation for millpy reviewer layer.

Imports WORKERS and REVIEWERS from their respective modules and validates
all invariants at import time. Any violation raises ValueError immediately
with a message naming the offending entry.

Validation invariants (per the import-time validation decision):
  1. Every Worker.provider is a key in BACKENDS.
  2. Worker.effort is None unless provider == "claude".
  3. Every Worker.dispatch_mode is in {"tool-use", "bulk"}.
  4. Every Ensemble.worker and Ensemble.handler is a valid WORKERS key.
  5. Every Ensemble.worker_count >= 1 (also enforced by __post_init__).
  6. Name-space non-overlap: WORKERS.keys() & REVIEWERS.keys() == set().
"""
from __future__ import annotations

from millpy.backends import BACKENDS
from millpy.reviewers.base import Ensemble, Worker
from millpy.reviewers.definitions import REVIEWERS
from millpy.reviewers.workers import WORKERS

__all__ = ["WORKERS", "REVIEWERS", "Worker", "Ensemble", "validate_registries"]

_VALID_DISPATCH_MODES = {"tool-use", "bulk"}


def validate_registries() -> None:
    """Validate WORKERS and REVIEWERS registries.

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

    # Invariant 4: Every Ensemble.worker and Ensemble.handler must be valid WORKERS keys.
    for name, ensemble in REVIEWERS.items():
        if ensemble.worker not in WORKERS:
            raise ValueError(
                f"REVIEWERS[{name!r}]: worker={ensemble.worker!r} is not a valid "
                f"WORKERS key"
            )
        if ensemble.handler not in WORKERS:
            raise ValueError(
                f"REVIEWERS[{name!r}]: handler={ensemble.handler!r} is not a valid "
                f"WORKERS key"
            )

    # Invariant 5: Every Ensemble.worker_count >= 1.
    for name, ensemble in REVIEWERS.items():
        if ensemble.worker_count < 1:
            raise ValueError(
                f"REVIEWERS[{name!r}]: worker_count={ensemble.worker_count} must be >= 1"
            )

    # Invariant 6: Name-space non-overlap.
    overlap = set(WORKERS.keys()) & set(REVIEWERS.keys())
    if overlap:
        raise ValueError(
            f"Name(s) appear in both WORKERS and REVIEWERS: {overlap} — "
            "names must be unique across both registries"
        )


# Run validation at import time.
validate_registries()
