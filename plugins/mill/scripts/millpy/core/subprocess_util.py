"""
subprocess_util.py — Single subprocess.run wrapper for millpy.

All subprocess invocations in millpy go through this wrapper.
Per the task constraint: encoding codified once.

Observability: every call emits structured spawn/exit log lines to stderr
via millpy.core.subprocess_logging. This is how the D.3 E2E smoke asserts
zero PS1 spawns (grep captured stderr for ``.ps1``).
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from millpy.core.subprocess_logging import log_exit, log_spawn


def run(
    argv: list[str],
    *,
    cwd: Path | str | None = None,
    input: str | None = None,
    check: bool = False,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with UTF-8 encoding and PYTHONIOENCODING set.

    Parameters
    ----------
    argv:
        Command and arguments to execute.
    cwd:
        Working directory for the subprocess. None uses the current directory.
    input:
        Optional string fed to the process's stdin.
    check:
        If True, raise CalledProcessError on non-zero exit code.
    timeout:
        Optional timeout in seconds.
    env:
        Optional environment dict. If None, inherits from os.environ.
        PYTHONIOENCODING=utf-8 is always injected.
    """
    child_env = env.copy() if env is not None else os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"

    log_spawn("subprocess_util", argv, timeout=timeout)
    start = time.monotonic()
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            input=input,
            check=check,
            timeout=timeout,
            env=child_env,
            encoding="utf-8",
            errors="replace",
            text=True,
            capture_output=True,
        )
    except subprocess.TimeoutExpired:
        log_exit(
            "subprocess_util",
            child_pid=-1,
            exit_code=-1,
            duration_seconds=time.monotonic() - start,
        )
        raise
    log_exit(
        "subprocess_util",
        child_pid=-1,
        exit_code=result.returncode,
        duration_seconds=time.monotonic() - start,
    )
    return result
