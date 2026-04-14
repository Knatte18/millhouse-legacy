"""
backends/gemini.py — Gemini CLI backend for millpy.

GeminiBackend implements the Backend Protocol. Bulk dispatch only — Gemini's
CLI rate limits make tool-use multi-turn unworkable. dispatch_tool_use raises
NotImplementedError.

Exit-code classification (historical from the pre-port spawn-agent shell script,
kept stable so downstream callers can depend on fixed codes):
  10 → rate-limit
  11 → bot-gate
  12 → binary-missing
  13 → unclassified

NOT unit-tested. Covered by live smoke.
"""
from __future__ import annotations

import os
from pathlib import Path

from millpy.backends.base import Backend, BulkResult, ToolUseResult
from millpy.core import subprocess_util
from millpy.core.log_util import log


# ---------------------------------------------------------------------------
# Exit code classification
# ---------------------------------------------------------------------------

def _classify_exit(exit_code: int) -> str | None:
    """Map a Gemini CLI exit code to a failure kind string.

    Returns None for exit code 0 (success). All other non-zero codes map to
    "unclassified" unless they match a known exit code.

    Parameters
    ----------
    exit_code:
        The process exit code.

    Returns
    -------
    str | None
        Failure kind string, or None on success.
    """
    _MAP = {
        10: "rate-limit",
        11: "bot-gate",
        12: "binary-missing",
        13: "unclassified",
    }
    if exit_code == 0:
        return None
    return _MAP.get(exit_code, "unclassified")


def _resolve_binary() -> str | None:
    """Resolve the gemini binary path.

    Precedence:
    1. MILLHOUSE_GEMINI_CLI env var (explicit override)
    2. 'gemini' on PATH (checked via shutil.which)
    """
    import shutil

    override = os.environ.get("MILLHOUSE_GEMINI_CLI")
    if override and Path(override).exists():
        return override
    return shutil.which("gemini")


# ---------------------------------------------------------------------------
# GeminiBackend
# ---------------------------------------------------------------------------

class GeminiBackend:
    """Gemini CLI backend implementing the Backend Protocol (bulk dispatch only).

    Uses `gemini -p - --model <model>` with prompt piped via stdin.
    """

    def dispatch_bulk(
        self,
        prompt: str,
        output_path: Path,
        *,
        model: str,
        effort: str | None,
    ) -> BulkResult:
        """Dispatch a bulk review prompt to the Gemini CLI.

        Parameters
        ----------
        prompt:
            Prompt text piped to gemini via stdin.
        output_path:
            File path where the gemini output is written.
        model:
            Gemini model name (e.g. "gemini-3-pro-preview").
        effort:
            Ignored — Gemini CLI does not support an effort parameter.

        Returns
        -------
        BulkResult
            Result with exit_code, stdout, stderr, and output_path.
            Non-zero exit codes are returned (not raised) so the caller
            can decide whether to fall back.
        """
        binary = _resolve_binary()
        if binary is None:
            log("gemini", "gemini binary not found; returning exit_code=12")
            return BulkResult(
                stdout="",
                stderr="gemini binary not found on PATH or MILLHOUSE_GEMINI_CLI",
                exit_code=12,
                output_path=output_path,
            )

        argv = [binary, "-p", "-", "--model", model]
        result = subprocess_util.run(argv, input=prompt)

        stdout_text = result.stdout.strip() if result.stdout else ""
        stderr_text = result.stderr.strip() if result.stderr else ""

        log(
            "gemini",
            f"bulk exit={result.returncode} "
            f"model={model} stderr_tail={stderr_text[-120:]!r}",
        )

        if result.returncode == 0 and stdout_text:
            output_path.write_text(stdout_text, encoding="utf-8")

        return BulkResult(
            stdout=stdout_text,
            stderr=stderr_text,
            exit_code=result.returncode,
            output_path=output_path,
        )

    def dispatch_tool_use(
        self,
        prompt: str,
        *,
        model: str,
        effort: str | None,
        max_turns: int,
    ) -> ToolUseResult:
        """Not implemented — Gemini uses bulk dispatch only.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError(
            "gemini provider uses bulk dispatch only in this task"
        )


# Satisfy the Backend Protocol at import time (structural check)
_: Backend = GeminiBackend()  # type: ignore[assignment]
