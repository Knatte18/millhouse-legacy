"""
log_util.py — stderr logging helper for millpy.

Stdout is reserved for entrypoint JSON-line contract. All informational
output goes to stderr. Named `log_util.py` (not `logging.py`) to avoid
shadowing Python's stdlib `logging` module — a classic gotcha that causes
subtle import-resolution bugs.
"""
from __future__ import annotations

import sys


def log(module: str, msg: str) -> None:
    """Write a bracketed log line to stderr.

    Writes `[{module}] {msg}` followed by a newline to sys.stderr and flushes
    immediately. Does not write to stdout.

    Parameters
    ----------
    module:
        Short name identifying the caller (e.g. "spawn-reviewer").
    msg:
        Message text. May be empty.
    """
    sys.stderr.write(f"[{module}] {msg}\n")
    sys.stderr.flush()
