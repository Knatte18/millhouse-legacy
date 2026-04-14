"""Tests for millpy.core.bulk_payload."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from millpy.core.bulk_payload import build_payload


def make_file(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


class TestBuildPayload:
    def test_empty_list_returns_empty_string(self, tmp_path):
        assert build_payload([], base_dir=tmp_path) == ""

    def test_single_file_header_and_line_numbers(self, tmp_path):
        p = make_file(tmp_path, "a.txt", "hello\nworld\n")
        result = build_payload([p], base_dir=tmp_path)
        assert "=== a.txt ===" in result
        assert "     1\thello" in result
        assert "     2\tworld" in result

    def test_multiple_files(self, tmp_path):
        p1 = make_file(tmp_path, "a.txt", "line1\n")
        p2 = make_file(tmp_path, "b.txt", "line2\n")
        result = build_payload([p1, p2], base_dir=tmp_path)
        assert "=== a.txt ===" in result and "=== b.txt ===" in result

    def test_utf8_and_subpath(self, tmp_path):
        p = make_file(tmp_path, "u.txt", "naïveté\n")
        result = build_payload([p], base_dir=tmp_path)
        assert "naïveté" in result
        # Subdirectory path uses forward slashes
        sub = tmp_path / "sub"
        sub.mkdir()
        p2 = sub / "f.py"
        p2.write_text("x\n", encoding="utf-8")
        result2 = build_payload([p2], base_dir=tmp_path)
        assert "=== sub/f.py ===" in result2

    def test_line_number_right_justified_6_chars(self, tmp_path):
        content = "".join(f"line{i}\n" for i in range(1, 12))
        p = make_file(tmp_path, "x.txt", content)
        result = build_payload([p], base_dir=tmp_path)
        assert "     1\tline1" in result
        assert "    10\tline10" in result

    def test_missing_file_raises_and_trailing_newline(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            build_payload([tmp_path / "missing.txt"], base_dir=tmp_path)
        p = make_file(tmp_path, "a.txt", "hello\n")
        assert build_payload([p], base_dir=tmp_path).endswith("\n")


class TestGrepGuard:
    """bulk_payload.py must not import git, subprocess, or git_ops."""

    def test_no_git_or_subprocess_imports(self):
        module_file = Path(__file__).parents[2] / "core" / "bulk_payload.py"
        source = module_file.read_text(encoding="utf-8")
        import_lines = [l for l in source.splitlines() if re.match(r"^\s*(import|from)\s+", l)]
        for line in import_lines:
            for forbidden in ("git", "git_ops", "subprocess"):
                assert forbidden not in line, f"forbidden import {forbidden!r} in: {line!r}"
