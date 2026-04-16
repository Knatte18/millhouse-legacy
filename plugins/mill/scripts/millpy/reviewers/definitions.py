"""
reviewers/definitions.py — REVIEWERS registry: ensemble compositions.

Each entry is a named Ensemble that references WORKERS entries by name.
Registry cross-validation (that referenced names exist in WORKERS) is
performed at import time in reviewers/__init__.py.

No cross-import with workers.py. The registries are wired together only in
__init__.py.

Naming convention
-----------------
Short-form names: "<worker>-x<count>-<handler>" (e.g. "g3flash-x3-sonnetmax").
"""
from __future__ import annotations

from millpy.reviewers.base import Ensemble

REVIEWERS: dict[str, Ensemble] = {
    "g3pro-x2-opus": Ensemble(
        worker="g3pro",
        worker_count=2,
        handler="opus",
    ),
    "g3flash-x3-sonnetmax": Ensemble(
        worker="g3flash",
        worker_count=3,
        handler="sonnetmax",
    ),
    "g3pro-x2-g3flash": Ensemble(
        worker="g3pro",
        worker_count=2,
        handler="g3flash",
    ),
    "g3flash-x3-g3flash": Ensemble(
        worker="g3flash",
        worker_count=3,
        handler="g3flash",
    ),
}
