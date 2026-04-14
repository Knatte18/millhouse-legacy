"""Tests for millpy.core.subprocess_util."""
from __future__ import annotations

import subprocess

import pytest

from millpy.core.subprocess_util import run


def test_happy_run_returns_stdout():
    result = run(["python", "-c", "print('hi')"])
    assert result.returncode == 0
    assert result.stdout == "hi\n"


def test_error_nonzero_returncode():
    result = run(["python", "-c", "import sys; sys.exit(7)"])
    assert result.returncode == 7


def test_check_true_raises():
    with pytest.raises(subprocess.CalledProcessError):
        run(["python", "-c", "import sys; sys.exit(7)"], check=True)


def test_child_receives_pythonioencoding():
    result = run(["python", "-c", "import os; print(os.environ['PYTHONIOENCODING'])"])
    assert result.stdout == "utf-8\n"
