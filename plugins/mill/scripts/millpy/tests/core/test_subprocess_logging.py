"""Tests for millpy.core.subprocess_logging — structured spawn/exit log lines."""
from __future__ import annotations

import sys

import pytest

from millpy.core.subprocess_logging import log_exit, log_spawn


def test_log_spawn_format(capsys):
    log_spawn("test_entry", ["git", "status"], timeout=5.0, parent_pid=12345)
    captured = capsys.readouterr()
    assert captured.out == ""
    expected = "[millpy.test_entry] spawning: git status  (timeout=5.0s, pid=12345)\n"
    assert captured.err == expected


def test_log_spawn_timeout_none_prints_none(capsys):
    log_spawn("test_entry", ["echo", "x"], timeout=None, parent_pid=1)
    captured = capsys.readouterr()
    assert "timeout=none" in captured.err


def test_log_spawn_shlex_joins_argv(capsys):
    log_spawn("test_entry", ["git", "commit", "-m", "hello world"], timeout=1.0, parent_pid=1)
    captured = capsys.readouterr()
    assert "git commit -m 'hello world'" in captured.err


def test_log_spawn_defaults_parent_pid_to_os_getpid(capsys):
    import os
    log_spawn("test_entry", ["true"], timeout=None)
    captured = capsys.readouterr()
    assert f"pid={os.getpid()}" in captured.err


def test_log_exit_format(capsys):
    log_exit("test_entry", child_pid=9876, exit_code=0, duration_seconds=1.234)
    captured = capsys.readouterr()
    expected = "[millpy.test_entry] child exited: pid=9876 exit-code=0 duration=1.2s\n"
    assert captured.err == expected


def test_log_exit_nonzero_exit(capsys):
    log_exit("test_entry", child_pid=100, exit_code=1, duration_seconds=0.5)
    captured = capsys.readouterr()
    assert "exit-code=1" in captured.err
    assert "pid=100" in captured.err


def test_log_exit_large_duration(capsys):
    log_exit("test_entry", child_pid=1, exit_code=0, duration_seconds=123.456)
    captured = capsys.readouterr()
    assert "duration=123.5s" in captured.err


def test_log_exit_unknown_pid_sentinel(capsys):
    """When the child PID is unknown (e.g. post-timeout), -1 is permitted."""
    log_exit("test_entry", child_pid=-1, exit_code=124, duration_seconds=30.0)
    captured = capsys.readouterr()
    assert "pid=-1" in captured.err
