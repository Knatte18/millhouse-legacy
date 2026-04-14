"""
reviewers/failures.py — Worker failure types and exit-code classification.

Provides:
  WorkerFailure — dataclass describing a single worker failure.
  KIND_* constants — canonical failure kind strings.
  classify_exit(exit_code) — maps exit codes to kind strings.
  is_malformed_output(stdout) — detects outputs that contain no review.

Exit code mapping mirrors spawn-agent.ps1:
  10  → rate-limit    (Gemini 429 / Claude rate limit)
  11  → bot-gate      (OAuth / policy block)
  12  → binary-missing
  13  → unclassified non-zero
  0   → None (success)
  other non-zero → unclassified
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KIND_RATE_LIMIT: str = "rate-limit"
KIND_BOT_GATE: str = "bot-gate"
KIND_BINARY_MISSING: str = "binary-missing"
KIND_UNCLASSIFIED: str = "unclassified"
KIND_MALFORMED: str = "malformed-output"
KIND_TIMEOUT: str = "timeout"

_EXIT_MAP: dict[int, str] = {
    10: KIND_RATE_LIMIT,
    11: KIND_BOT_GATE,
    12: KIND_BINARY_MISSING,
    13: KIND_UNCLASSIFIED,
}

_VERDICT_RE = re.compile(r"^VERDICT:", re.MULTILINE)


# ---------------------------------------------------------------------------
# WorkerFailure dataclass
# ---------------------------------------------------------------------------

@dataclass
class WorkerFailure:
    """Describes a single worker failure.

    Fields
    ------
    kind:
        Failure classification (one of the KIND_* constants).
    detail:
        Human-readable detail string.
    exit_code:
        Process exit code.
    stderr_tail:
        Last N characters of stderr for diagnostics.
    """

    kind: str
    detail: str
    exit_code: int
    stderr_tail: str


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def classify_exit(exit_code: int) -> str | None:
    """Map a process exit code to a failure kind string.

    Parameters
    ----------
    exit_code:
        The exit code from the worker subprocess.

    Returns
    -------
    str | None
        A KIND_* constant, or None if exit_code == 0 (success).
    """
    if exit_code == 0:
        return None
    return _EXIT_MAP.get(exit_code, KIND_UNCLASSIFIED)


def is_malformed_output(stdout: str) -> bool:
    """Return True if stdout contains no parseable review.

    A review is considered present if stdout contains either:
    - A parseable JSON object, or
    - A line matching ``VERDICT: ...``

    Parameters
    ----------
    stdout:
        Raw stdout from the worker process.

    Returns
    -------
    bool
        True if the output is considered malformed (no review content).
    """
    if not stdout:
        return True

    # Check for VERDICT: line
    if _VERDICT_RE.search(stdout):
        return False

    # Check for any parseable JSON object in the output
    # Look for {...} in the text
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                json.loads(stripped)
                return False
            except json.JSONDecodeError:
                pass

    # Try parsing the whole stdout as JSON
    try:
        obj = json.loads(stdout.strip())
        if isinstance(obj, dict):
            return False
    except json.JSONDecodeError:
        pass

    return True
