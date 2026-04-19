"""
reviewers/clusters.py — CLUSTERS registry: cluster compositions.

Each entry is a named Cluster that references WORKERS entries by name.
Registry cross-validation (that referenced names exist in WORKERS) is
performed at import time in reviewers/__init__.py.

No cross-import with workers.py. The registries are wired together only in
__init__.py.

Naming convention
-----------------
Short-form names: "<worker>-x<count>-<handler>" (e.g. "g3flash-x3-sonnetmax").
"""
from __future__ import annotations

from millpy.reviewers.base import Cluster

CLUSTERS: dict[str, Cluster] = {
    "g3pro-x2-opus": Cluster(
        worker="g3pro",
        worker_count=2,
        handler="opus",
    ),
    "g3flash-x3-sonnetmax": Cluster(
        worker="g3flash",
        worker_count=3,
        handler="sonnetmax",
    ),
    "g3pro-x2-g3flash": Cluster(
        worker="g3pro",
        worker_count=2,
        handler="g3flash",
    ),
    "g3flash-x3-g3flash": Cluster(
        worker="g3flash",
        worker_count=3,
        handler="g3flash",
    ),
    "g25flash-x3-sonnetmax": Cluster(
        worker="g25flash",
        worker_count=3,
        handler="sonnetmax",
        handler_prep=True,
    ),
    "g25flash-x3-g25flash": Cluster(
        worker="g25flash",
        worker_count=3,
        handler="g25flash",
    ),
    "g25pro-x2-g25flash": Cluster(
        worker="g25pro",
        worker_count=2,
        handler="g25flash",
    ),
    "haiku-x3-sonnetmax": Cluster(
        worker="haiku",
        worker_count=3,
        handler="sonnetmax",
        handler_prep=True,
    ),
    "g25flash-x1-sonnetmax": Cluster(
        worker="g25flash",
        worker_count=1,
        handler="sonnetmax",
        handler_prep=True,
    ),
    "g25flash-x3-sonnet": Cluster(
        worker="g25flash",
        worker_count=3,
        handler="sonnet",
        handler_prep=True,
    ),
}
