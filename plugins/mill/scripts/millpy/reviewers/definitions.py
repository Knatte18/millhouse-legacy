"""
reviewers/definitions.py — REVIEWERS registry: ensemble compositions.

Each entry is a named Ensemble that references WORKERS entries by name.
Registry cross-validation (that referenced names exist in WORKERS) is
performed at import time in reviewers/__init__.py.

No cross-import with workers.py. The registries are wired together only in
__init__.py.
"""
from __future__ import annotations

from millpy.reviewers.base import Ensemble

REVIEWERS: dict[str, Ensemble] = {
    "ensemble-gemini3pro-x2-opus": Ensemble(
        worker="gemini3pro",
        worker_count=2,
        handler="opus",
    ),
    "ensemble-gemini3flash-x3-sonnetmax": Ensemble(
        worker="gemini3flash",
        worker_count=3,
        handler="sonnetmax",
    ),
    "ensemble-gemini3pro-x2-gemini3flash": Ensemble(
        worker="gemini3pro",
        worker_count=2,
        handler="gemini3flash",
    ),
}
