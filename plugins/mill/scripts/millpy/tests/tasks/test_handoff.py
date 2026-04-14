"""
test_handoff.py — Tests for millpy.tasks.handoff (TDD: RED → GREEN → REFACTOR).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from millpy.tasks.handoff import materialize


class TestMaterialize:
    def test_creates_file(self, tmp_path):
        out = tmp_path / "handoff.md"
        materialize("My Task", "Description here.", "planned", out)
        assert out.exists()

    def test_contains_task_title(self, tmp_path):
        out = tmp_path / "handoff.md"
        materialize("My Task", "Description here.", "planned", out)
        text = out.read_text(encoding="utf-8")
        assert "My Task" in text

    def test_contains_phase(self, tmp_path):
        out = tmp_path / "handoff.md"
        materialize("My Task", "Description here.", "planned", out)
        text = out.read_text(encoding="utf-8")
        assert "planned" in text

    def test_contains_timestamp(self, tmp_path):
        import re
        out = tmp_path / "handoff.md"
        materialize("My Task", "Description here.", "planned", out)
        text = out.read_text(encoding="utf-8")
        assert re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", text)

    def test_multiline_description(self, tmp_path):
        out = tmp_path / "handoff.md"
        materialize("My Task", "Line 1\nLine 2", "planned", out)
        text = out.read_text(encoding="utf-8")
        assert "Line 1" in text
        assert "Line 2" in text

    def test_utf8_content(self, tmp_path):
        out = tmp_path / "handoff.md"
        materialize("Naïve Task", "Café résumé", "planned", out)
        text = out.read_text(encoding="utf-8")
        assert "Naïve" in text
        assert "Café" in text

    def test_contains_description_section(self, tmp_path):
        out = tmp_path / "handoff.md"
        materialize("My Task", "Description here.", "planned", out)
        text = out.read_text(encoding="utf-8")
        assert "## Description" in text

    def test_raises_on_unwritable_path(self, tmp_path):
        # Path whose parent doesn't exist
        out = tmp_path / "nonexistent" / "handoff.md"
        with pytest.raises(OSError):
            materialize("My Task", "Desc.", "planned", out)
