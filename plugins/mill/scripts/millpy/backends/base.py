"""
backends/base.py — Backend Protocol and result types for millpy.

Pure types and protocols — no implementation. All concrete backends implement
the Backend Protocol. BulkResult and ToolUseResult are frozen dataclasses so
callers cannot accidentally mutate result objects after return.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BulkResult:
    """Result from a bulk dispatch (gemini/ollama bulk mode)."""

    stdout: str
    stderr: str
    exit_code: int
    output_path: Path


@dataclass(frozen=True)
class ToolUseResult:
    """Result from a tool-use dispatch (claude/ollama tool-use mode)."""

    result_text: str
    parsed_json: dict | None
    exit_code: int
    raw_stdout: str
    raw_stderr: str
    session_id: str | None = None


# ---------------------------------------------------------------------------
# Backend Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class Backend(Protocol):
    """Protocol that all backend implementations must satisfy.

    @runtime_checkable so isinstance(x, Backend) works for registry validation.
    """

    def dispatch_bulk(
        self,
        prompt: str,
        output_path: Path,
        *,
        model: str,
        effort: str | None,
    ) -> BulkResult:
        """Send a bulk (non-interactive) review prompt to the backend.

        Parameters
        ----------
        prompt:
            The full prompt text to send.
        output_path:
            File path where the output should be written.
        model:
            Model identifier string (e.g. "sonnet", "gemini-3-pro").
        effort:
            Optional effort level (claude only: "low"|"medium"|"high"|"max").
        """
        ...

    def dispatch_tool_use(
        self,
        prompt: str,
        *,
        model: str,
        effort: str | None,
        max_turns: int,
    ) -> ToolUseResult:
        """Send an interactive tool-use prompt to the backend.

        Parameters
        ----------
        prompt:
            The full prompt text to send via stdin.
        model:
            Model identifier string.
        effort:
            Optional effort level (claude only).
        max_turns:
            Maximum number of tool-use turns before stopping.
        """
        ...

    def dispatch_tool_use_resume(
        self,
        session_id: str,
        prompt: str,
        *,
        model: str,
        effort: str | None,
        max_turns: int,
    ) -> ToolUseResult:
        """Resume a previous tool-use session with a new prompt.

        Parameters
        ----------
        session_id:
            Session ID returned by a previous dispatch_tool_use call.
        prompt:
            New prompt text to send to the resumed session via stdin.
        model:
            Model identifier string.
        effort:
            Optional effort level (claude only).
        max_turns:
            Maximum number of tool-use turns before stopping.
        """
        ...


# ---------------------------------------------------------------------------
# BackendError
# ---------------------------------------------------------------------------

class BackendError(Exception):
    """Raised when a backend encounters a classified failure.

    Attributes
    ----------
    kind:
        Failure classification (e.g. "rate-limit", "bot-gate",
        "binary-missing", "unclassified").
    detail:
        Human-readable detail string.
    """

    def __init__(self, *, kind: str, detail: str) -> None:
        super().__init__(f"[{kind}] {detail}")
        self.kind = kind
        self.detail = detail
