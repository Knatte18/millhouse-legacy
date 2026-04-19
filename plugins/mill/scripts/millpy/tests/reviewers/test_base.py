"""Tests for millpy.reviewers.base — Worker, Cluster, Reviewer, ReviewerResult."""
from __future__ import annotations

import pytest

from millpy.reviewers.base import Cluster, Worker


class TestWorkerDefaults:
    def test_claude_default_dispatch_mode(self):
        w = Worker(provider="claude", model="sonnet")
        assert w.dispatch_mode == "tool-use"

    def test_gemini_default_dispatch_mode(self):
        w = Worker(provider="gemini", model="gemini-3-pro-preview")
        assert w.dispatch_mode == "bulk"

    def test_ollama_default_dispatch_mode(self):
        w = Worker(provider="ollama", model="glm-4.7-flash:latest")
        assert w.dispatch_mode == "tool-use"

    def test_max_turns_default(self):
        w = Worker(provider="claude", model="sonnet")
        assert w.max_turns == 30

    def test_max_turns_override(self):
        w = Worker(provider="claude", model="sonnet", max_turns=50)
        assert w.max_turns == 50

    def test_dispatch_mode_override_preserved(self):
        w = Worker(provider="claude", model="sonnet", dispatch_mode="bulk")
        assert w.dispatch_mode == "bulk"

    def test_effort_default_none(self):
        w = Worker(provider="claude", model="sonnet")
        assert w.effort is None


class TestWorkerFrozen:
    def test_extras_mutation_raises(self):
        """extras wrapped in MappingProxyType must raise TypeError on mutation."""
        w = Worker(provider="ollama", model="qwen3:30b-thinking", extras={"think": True})
        with pytest.raises(TypeError):
            w.extras["think"] = False  # type: ignore[index]

    def test_extras_read(self):
        w = Worker(provider="ollama", model="qwen3:30b-thinking", extras={"think": True})
        assert w.extras["think"] is True


class TestCluster:
    def test_worker_count_zero_raises(self):
        with pytest.raises(ValueError):
            Cluster(worker="sonnet", worker_count=0, handler="opus")

    def test_worker_count_one_allowed(self):
        e = Cluster(worker="sonnet", worker_count=1, handler="opus")
        assert e.worker_count == 1

    def test_handler_prep_default_false(self):
        e = Cluster(worker="sonnet", worker_count=2, handler="opus")
        assert e.handler_prep is False


class TestWorkerProviderDefaults:
    """Verify all three providers get their correct defaults."""

    def test_claude_tool_use(self):
        assert Worker(provider="claude", model="x").dispatch_mode == "tool-use"

    def test_gemini_bulk(self):
        assert Worker(provider="gemini", model="x").dispatch_mode == "bulk"

    def test_ollama_tool_use(self):
        assert Worker(provider="ollama", model="x").dispatch_mode == "tool-use"
