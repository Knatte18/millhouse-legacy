"""Regression — spawn_task does not write a `discussion.md` placeholder.

Before 2026-04-16, spawn_task emitted an empty `.millhouse/task/discussion.md`
shell file. That forced mill-start to use `Edit` on a pre-existing file
instead of writing fresh, which caused a "must Read before Edit" protocol
error the first time Claude touched it.

This test pins both the function removal and the call-site removal.
"""
from __future__ import annotations

from millpy.entrypoints import spawn_task


def test_write_discussion_placeholder_function_is_removed():
    """`_write_discussion_placeholder` is gone from the module namespace."""
    assert not hasattr(spawn_task, "_write_discussion_placeholder")


def test_spawn_task_source_has_no_call_site():
    """Belt-and-suspenders — source text no longer references the removed helper."""
    from pathlib import Path

    source = Path(spawn_task.__file__).read_text(encoding="utf-8")
    assert "_write_discussion_placeholder" not in source
    assert "Write discussion placeholder" not in source
