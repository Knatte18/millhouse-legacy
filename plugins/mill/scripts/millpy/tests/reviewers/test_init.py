"""Tests for millpy.reviewers.__init__ import-time validation."""
from __future__ import annotations

import pytest

from millpy.reviewers.base import Cluster, Worker
from millpy.reviewers.clusters import CLUSTERS
from millpy.reviewers.workers import WORKERS


def test_import_succeeds():
    """Importing millpy.reviewers should not raise."""
    import millpy.reviewers  # noqa: F401


def test_validate_registries_no_error():
    """validate_registries() should pass with the current registries."""
    from millpy.reviewers import validate_registries
    validate_registries()  # must not raise


class TestWorkerProviderValidation:
    def test_bad_provider_raises(self, clean_registries):
        """Worker with unknown provider raises ValueError on validate_registries."""
        from millpy.reviewers import validate_registries
        WORKERS["bogus-provider"] = Worker(provider="unknown-backend", model="x")
        with pytest.raises(ValueError, match="bogus-provider"):
            validate_registries()

    def test_effort_on_non_claude_raises(self, clean_registries):
        """effort != None on non-claude provider raises ValueError."""
        from millpy.reviewers import validate_registries
        # Must bypass frozen dataclass by constructing with valid provider first
        # We use object.__setattr__ trick; instead just add directly to WORKERS
        # with a gemini worker that has effort set (can't be constructed normally
        # since __post_init__ doesn't block it, only validate_registries does)
        WORKERS["bogus"] = Worker.__new__(Worker)
        object.__setattr__(WORKERS["bogus"], "provider", "gemini")
        object.__setattr__(WORKERS["bogus"], "model", "x")
        object.__setattr__(WORKERS["bogus"], "effort", "max")
        object.__setattr__(WORKERS["bogus"], "dispatch_mode", "bulk")
        object.__setattr__(WORKERS["bogus"], "max_turns", 30)
        object.__setattr__(WORKERS["bogus"], "extras", {})
        with pytest.raises(ValueError, match="bogus"):
            validate_registries()

    def test_claude_with_effort_ok(self, clean_registries):
        """claude worker with effort is valid."""
        from millpy.reviewers import validate_registries
        WORKERS["claude-effort-ok"] = Worker(provider="claude", model="x", effort="max")
        validate_registries()  # must not raise


class TestClusterValidation:
    def test_ensemble_bad_worker_name_raises(self, clean_registries):
        """Cluster referencing non-existent WORKERS key raises ValueError."""
        from millpy.reviewers import validate_registries
        CLUSTERS["bogus-ensemble"] = Cluster(
            worker="nonexistent",
            worker_count=1,
            handler="opus",
        )
        with pytest.raises(ValueError, match="bogus-ensemble"):
            validate_registries()

    def test_ensemble_bad_handler_name_raises(self, clean_registries):
        """Cluster with non-existent handler WORKERS key raises ValueError."""
        from millpy.reviewers import validate_registries
        CLUSTERS["bad-handler"] = Cluster(
            worker="sonnet",
            worker_count=1,
            handler="nonexistent-handler",
        )
        with pytest.raises(ValueError, match="bad-handler"):
            validate_registries()


class TestNamespaceOverlap:
    def test_name_in_both_raises(self, clean_registries):
        """Name appearing in both WORKERS and CLUSTERS raises ValueError."""
        from millpy.reviewers import validate_registries
        # Add "foo" to both
        WORKERS["foo"] = Worker(provider="claude", model="x")
        CLUSTERS["foo"] = Cluster(worker="sonnet", worker_count=1, handler="opus")
        with pytest.raises(ValueError, match="foo"):
            validate_registries()


class TestDispatchModeValidation:
    def test_invalid_dispatch_mode_raises(self, clean_registries):
        """Worker with dispatch_mode not in {tool-use, bulk} raises ValueError."""
        from millpy.reviewers import validate_registries
        w = Worker.__new__(Worker)
        object.__setattr__(w, "provider", "claude")
        object.__setattr__(w, "model", "x")
        object.__setattr__(w, "effort", None)
        object.__setattr__(w, "dispatch_mode", "invalid-mode")
        object.__setattr__(w, "max_turns", 30)
        object.__setattr__(w, "extras", {})
        WORKERS["bad-mode"] = w
        with pytest.raises(ValueError, match="bad-mode"):
            validate_registries()


class TestExports:
    def test_all_exports(self):
        """__all__ contains the required symbols."""
        import millpy.reviewers as r
        for sym in ("WORKERS", "CLUSTERS", "Worker", "Cluster", "validate_registries"):
            assert sym in dir(r), f"{sym!r} not in reviewers namespace"
