"""
test_status_md.py — Tests for millpy.tasks.status_md (TDD: RED → GREEN → REFACTOR).
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from millpy.tasks.status_md import append_timeline, load, save, update_phase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

STATUS_BASIC = """\
# Status

```yaml
task: My Task
phase: implementing
parent: main
discussion: _millhouse/task/discussion.md
plan: _millhouse/task/plan.md
task_description: |
  Python toolkit — retire PowerShell scripts
```

## Timeline

```text
discussing              2026-04-14T08:15:19Z
implementing            2026-04-14T17:57:30Z
```
"""

STATUS_WITH_NESTED = """\
# Status

```yaml
task: Nested Task
phase: implementing
parent: main
current_subprocess:
  pid: 12345
  phase: implementing
  started: 2026-04-14T10:00:00Z
```

## Timeline

```text
implementing            2026-04-14T10:00:00Z
```
"""

STATUS_NO_YAML = """\
# Status

Some text without a yaml block.

## Timeline
"""


def write_status(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "status.md"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------

class TestLoad:
    def test_loads_basic_fields(self, tmp_path):
        p = write_status(tmp_path, STATUS_BASIC)
        data = load(p)
        assert data["task"] == "My Task"
        assert data["phase"] == "implementing"
        assert data["parent"] == "main"

    def test_loads_multiline_task_description(self, tmp_path):
        p = write_status(tmp_path, STATUS_BASIC)
        data = load(p)
        assert "Python toolkit" in data["task_description"]

    def test_loads_nested_mapping(self, tmp_path):
        p = write_status(tmp_path, STATUS_WITH_NESTED)
        data = load(p)
        assert isinstance(data["current_subprocess"], dict)
        assert data["current_subprocess"]["pid"] == 12345
        assert data["current_subprocess"]["phase"] == "implementing"

    def test_raises_on_no_yaml_block(self, tmp_path):
        p = write_status(tmp_path, STATUS_NO_YAML)
        with pytest.raises(Exception):
            load(p)

    def test_smoke_real_status(self):
        """Smoke: loads the worktree's own status.md if present."""
        status_path = Path(__file__).parents[5] / "_millhouse" / "task" / "status.md"
        if status_path.exists():
            data = load(status_path)
            assert "phase" in data


# ---------------------------------------------------------------------------
# save()
# ---------------------------------------------------------------------------

class TestSave:
    def test_round_trip_basic(self, tmp_path):
        p = write_status(tmp_path, STATUS_BASIC)
        data = load(p)
        save(p, data)
        data2 = load(p)
        assert data2["phase"] == data["phase"]
        assert data2["task"] == data["task"]

    def test_preserves_timeline_section(self, tmp_path):
        p = write_status(tmp_path, STATUS_BASIC)
        data = load(p)
        save(p, data)
        text = p.read_text(encoding="utf-8")
        assert "## Timeline" in text
        assert "```text" in text

    def test_preserves_multiline_scalar(self, tmp_path):
        p = write_status(tmp_path, STATUS_BASIC)
        data = load(p)
        save(p, data)
        data2 = load(p)
        assert "Python toolkit" in data2["task_description"]


# ---------------------------------------------------------------------------
# update_phase()
# ---------------------------------------------------------------------------

class TestUpdatePhase:
    def test_updates_phase(self, tmp_path):
        p = write_status(tmp_path, STATUS_BASIC)
        update_phase(p, "testing")
        data = load(p)
        assert data["phase"] == "testing"

    def test_preserves_other_fields(self, tmp_path):
        p = write_status(tmp_path, STATUS_BASIC)
        update_phase(p, "testing")
        data = load(p)
        assert data["task"] == "My Task"
        assert "Python toolkit" in data["task_description"]


# ---------------------------------------------------------------------------
# append_timeline()
# ---------------------------------------------------------------------------

class TestAppendTimeline:
    def test_appends_entry(self, tmp_path):
        p = write_status(tmp_path, STATUS_BASIC)
        append_timeline(p, "testing")
        text = p.read_text(encoding="utf-8")
        assert "testing" in text

    def test_entry_before_closing_fence(self, tmp_path):
        p = write_status(tmp_path, STATUS_BASIC)
        append_timeline(p, "testing")
        text = p.read_text(encoding="utf-8")
        # The closing ``` must come after the new entry
        testing_idx = text.rfind("testing")
        fence_idx = text.rfind("```")
        assert testing_idx < fence_idx

    def test_existing_entries_preserved(self, tmp_path):
        p = write_status(tmp_path, STATUS_BASIC)
        append_timeline(p, "testing")
        text = p.read_text(encoding="utf-8")
        assert "discussing" in text
        assert "implementing" in text

    def test_entry_contains_timestamp(self, tmp_path):
        p = write_status(tmp_path, STATUS_BASIC)
        append_timeline(p, "testing")
        text = p.read_text(encoding="utf-8")
        import re
        # Should contain a UTC timestamp like 2026-04-14T...Z
        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", text)
