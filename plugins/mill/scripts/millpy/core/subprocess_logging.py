"""
subprocess_logging.py — Structured spawn/exit log lines for millpy subprocess calls.

Two pure side-effect functions that write one-line stderr log entries per
subprocess lifecycle event. Called from ``subprocess_util.run`` so every
production subprocess in millpy is observable after the fact.

Log format:
    [millpy.<entrypoint>] spawning: <shlex-joined-cmd>  (timeout=<N>s, pid=<parent-pid>)
    [millpy.<entrypoint>] child exited: pid=<child-pid> exit-code=<N> duration=<N.Ns>

Rationale: the recurring "script doesn't return" bug class is invisible
until you reproduce the hang. These log lines make failures diagnosable
after the fact without re-running. They also double as the zero-PS1
assertion surface for D.3 — grep captured stderr for ``.ps1`` and any
match is a test failure.
"""
from __future__ import annotations

import os
import shlex
import sys


def _format_cmd(cmd: list[str]) -> str:
    """Join a command argv list into a single shlex-quoted string."""
    return shlex.join(cmd)


def log_spawn(
    entrypoint: str,
    cmd: list[str],
    timeout: float | None,
    parent_pid: int | None = None,
) -> None:
    """Log a subprocess spawn event to stderr.

    Parameters
    ----------
    entrypoint:
        Name of the millpy module / entrypoint spawning the child
        (e.g. ``"subprocess_util"``, ``"spawn_agent"``).
    cmd:
        The argv list being passed to subprocess.Popen / subprocess.run.
    timeout:
        The configured timeout in seconds, or None for no timeout.
    parent_pid:
        Optional parent PID. Defaults to ``os.getpid()`` when None.
    """
    pid = os.getpid() if parent_pid is None else parent_pid
    timeout_str = f"{timeout}s" if timeout is not None else "none"
    print(
        f"[millpy.{entrypoint}] spawning: {_format_cmd(cmd)}  "
        f"(timeout={timeout_str}, pid={pid})",
        file=sys.stderr,
        flush=True,
    )


def log_exit(
    entrypoint: str,
    child_pid: int,
    exit_code: int,
    duration_seconds: float,
) -> None:
    """Log a subprocess exit event to stderr.

    Parameters
    ----------
    entrypoint:
        Name of the millpy module / entrypoint that spawned the child.
    child_pid:
        PID of the child process that exited. Use ``-1`` when the PID
        is unknown (e.g. synthesized after a TimeoutExpired).
    exit_code:
        Exit code returned by the child, or a synthesized code on timeout.
    duration_seconds:
        Elapsed wall-clock time from spawn to exit, in seconds.
    """
    print(
        f"[millpy.{entrypoint}] child exited: "
        f"pid={child_pid} exit-code={exit_code} duration={duration_seconds:.1f}s",
        file=sys.stderr,
        flush=True,
    )
