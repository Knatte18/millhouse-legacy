"""
conftest.py — pytest fixtures for reviewers tests.

The clean_registries fixture snapshots WORKERS and CLUSTERS before each test
and restores them on teardown. Required for any test that mutates the registries
at module level to avoid polluting subsequent tests.
"""
from __future__ import annotations

import pytest

from millpy.reviewers.clusters import CLUSTERS
from millpy.reviewers.workers import WORKERS


@pytest.fixture
def clean_registries():
    """Snapshot WORKERS and REVIEWERS, restore them after each test.

    Use this fixture in every test that mutates WORKERS or CLUSTERS to prevent
    state leakage into subsequent tests in the same pytest session.
    """
    snapshot_w = dict(WORKERS)
    snapshot_r = dict(CLUSTERS)
    yield
    WORKERS.clear()
    WORKERS.update(snapshot_w)
    CLUSTERS.clear()
    CLUSTERS.update(snapshot_r)
