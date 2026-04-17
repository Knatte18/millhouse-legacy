"""Unit tests for millpy.entrypoints.spawn_task.pick_task.

The pure helper that decides between fast-path ([s]) and numbered-fallback
(unmarked tasks). No filesystem, no git — just Task instances in memory.
"""
from __future__ import annotations

from millpy.entrypoints.spawn_task import pick_task
from millpy.tasks.tasks_md import Task


def _t(title: str, phase: str | None) -> Task:
    """Shorthand Task constructor for tests (body and line_number irrelevant here)."""
    return Task(title=title, phase=phase, body="", line_number=1)


class TestPickTaskFastPath:
    def test_first_s_task_is_picked_with_mode_fast_path(self):
        tasks = [_t("A", None), _t("B", "s"), _t("C", "active")]
        mode, picked, candidates = pick_task(tasks)
        assert mode == "fast-path"
        assert picked is tasks[1]
        assert candidates == []

    def test_multiple_s_tasks_picks_the_first_one(self):
        tasks = [_t("A", "s"), _t("B", "s"), _t("C", None)]
        mode, picked, candidates = pick_task(tasks)
        assert mode == "fast-path"
        assert picked is tasks[0]
        assert candidates == []

    def test_active_alongside_s_is_filtered_and_not_prompted(self):
        """Regression: the [active] task must not leak into candidates or picks."""
        tasks = [_t("A", "s"), _t("B", "active")]
        mode, picked, candidates = pick_task(tasks)
        assert mode == "fast-path"
        assert picked is tasks[0]
        assert candidates == []


class TestPickTaskNumbered:
    def test_only_unmarked_tasks_become_candidates(self):
        tasks = [_t("A", None), _t("B", None), _t("C", "active")]
        mode, picked, candidates = pick_task(tasks)
        assert mode == "numbered"
        assert picked is None
        assert [t.title for t in candidates] == ["A", "B"]

    def test_done_and_abandoned_are_filtered_out(self):
        tasks = [_t("Keep", None), _t("Done", "done"), _t("Abn", "abandoned")]
        mode, picked, candidates = pick_task(tasks)
        assert mode == "numbered"
        assert [t.title for t in candidates] == ["Keep"]


class TestPickTaskEmpty:
    def test_empty_tasks_list(self):
        mode, picked, candidates = pick_task([])
        assert mode == "empty"
        assert picked is None
        assert candidates == []

    def test_only_active_done_abandoned_tasks_is_empty(self):
        tasks = [_t("A", "active"), _t("D", "done"), _t("X", "abandoned")]
        mode, picked, candidates = pick_task(tasks)
        assert mode == "empty"
        assert picked is None
        assert candidates == []
