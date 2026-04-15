"""
reviewers/definitions.py — REVIEWERS registry: ensemble compositions.

Each entry is a named Ensemble that references WORKERS entries by name.
Registry cross-validation (that referenced names exist in WORKERS) is
performed at import time in reviewers/__init__.py.

No cross-import with workers.py. The registries are wired together only in
__init__.py.

Naming convention
-----------------
Canonical short-form names (e.g. "g3flash-x3-sonnetmax-plan") are preferred
for new entries. The legacy "ensemble-*" keys are retained for pre-W1 config
compatibility but all new entries use the short form.

Note on "g3flash-x3-sonnetmax-plan"
------------------------------------
This ensemble uses bulk-dispatch Flash workers. If a user configures it as
``pipeline.plan-review.default``, the ``_guard_plan_whole_bulk`` guard in
engine.py will reject the whole-plan reviewer slice with a ConfigError because
whole-plan review requires tool-use dispatch. The intended W2 usage is a
tool-use single-worker (``sonnet`` or ``sonnetmax``) as the plan-review
default; this ensemble is registered for future per-batch bulk dispatch.
"""
from __future__ import annotations

from millpy.reviewers.base import Ensemble

REVIEWERS: dict[str, Ensemble] = {
    # Legacy keys — retained for pre-W1 config compatibility.
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
    # Canonical short-form entries (W2+).
    "g3flash-x3-sonnetmax-plan": Ensemble(
        worker="gemini3flash",
        worker_count=3,
        handler="sonnetmax",
    ),
}
