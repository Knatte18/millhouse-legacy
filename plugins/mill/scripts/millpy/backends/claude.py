"""
backends/claude.py — Claude CLI backend for millpy.

ClaudeBackend implements the Backend Protocol via `claude -p`. The pure helper
_parse_claude_json_wrapper is extracted for unit-testability (this is the exact
bug class that motivated the Python rewrite — markdown-backtick wrapping and
scalar unboxing quirks).
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path

from millpy.backends.base import Backend, BulkResult, ToolUseResult
from millpy.core import subprocess_util
from millpy.core.log_util import log


def _resolve_claude_binary() -> str:
    """Resolve the `claude` executable via shutil.which.

    shutil.which honors PATHEXT per-directory order so a `claude.cmd` test
    fixture on PATH wins over a real `claude.exe` later in PATH. Falls
    back to the literal string "claude" if shutil.which returns None,
    which lets CreateProcess's own search kick in (same behavior as
    before this helper was introduced).
    """
    resolved = shutil.which("claude")
    return resolved if resolved else "claude"


# ---------------------------------------------------------------------------
# Pure helper — unit-tested
# ---------------------------------------------------------------------------

def _parse_claude_json_wrapper(stdout: str) -> tuple[dict, str | None]:
    """Parse the JSON wrapper emitted by `claude -p --output-format json`.

    The claude CLI wraps the agent's result text in:
        {"result": "<agent-output>", "session_id": "...", "cost": ..., ...}

    The agent's output may itself be:
      1. Plain JSON (already valid)
      2. Wrapped in single backticks: `{...}`
      3. Wrapped in triple backticks (with optional language marker):
           ```json
           {...}
           ```
      4. Prose with a JSON object on the last parseable line (fallback)

    Parameters
    ----------
    stdout:
        Raw stdout from `claude -p --output-format json`.

    Returns
    -------
    tuple[dict, str | None]
        A 2-tuple of (parsed_inner_dict, session_id). session_id is None when
        the outer wrapper does not contain a ``session_id`` field or when
        stdout is not valid JSON (fallback path).

    Raises
    ------
    ValueError
        If result is empty, null, or no JSON can be extracted from stdout.
    """
    # --- Parse the outer JSON wrapper ---
    try:
        wrapper = json.loads(stdout)
    except json.JSONDecodeError:
        # stdout itself is not JSON — scan lines for last JSON object
        return _fallback_line_scan(stdout, context="unparseable"), None

    # Extract session_id from the outer wrapper (present in real claude output)
    raw_session_id = wrapper.get("session_id")
    session_id: str | None = raw_session_id if isinstance(raw_session_id, str) else None

    result_raw = wrapper.get("result")

    if result_raw is None:
        raise ValueError("null result: claude returned null in 'result' field")

    if not isinstance(result_raw, str):
        # Scalar unboxing: the result was already parsed as a non-string JSON value
        # Treat it as a JSON value and wrap it back
        if isinstance(result_raw, dict):
            return result_raw, session_id
        raise ValueError(
            f"unparseable result: expected string in 'result' field, got {type(result_raw).__name__}"
        )

    result_text = result_raw.strip()
    if not result_text:
        raise ValueError("empty result: claude returned empty string in 'result' field")

    return _parse_result_text(result_text), session_id


def _parse_result_text(text: str) -> dict:
    """Parse the agent result text into a dict.

    Handles single-backtick, triple-backtick, direct JSON, and fallback scan.
    """
    # Strip triple-backtick fences (with optional language marker)
    triple_match = re.match(r"^```(?:[a-z]*)?\n?(.*?)\n?```$", text, re.DOTALL)
    if triple_match:
        inner = triple_match.group(1).strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            pass

    # Strip single-backtick wrapping
    if text.startswith("`") and text.endswith("`") and len(text) >= 2:
        inner = text[1:-1].strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            pass

    # Try parsing the entire text as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: scan lines from the end for the last parseable JSON object
    return _fallback_line_scan(text, context="unparseable stdout")


def _fallback_line_scan(text: str, context: str) -> dict:
    """Scan lines from the end, return the last line that parses as JSON dict."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    raise ValueError(f"unparseable stdout: {context} — no JSON object found in output")


# ---------------------------------------------------------------------------
# ClaudeBackend
# ---------------------------------------------------------------------------

class ClaudeBackend:
    """Claude CLI backend implementing the Backend Protocol.

    Uses `claude -p --output-format json` for tool-use dispatch and
    `claude -p --output-format text` for bulk dispatch.
    """

    def dispatch_tool_use(
        self,
        prompt: str,
        *,
        model: str,
        effort: str | None,
        max_turns: int,
    ) -> ToolUseResult:
        """Run claude -p with tool-use mode, parse JSON wrapper output.

        Parameters
        ----------
        prompt:
            Prompt text sent to claude via stdin.
        model:
            Model name (e.g. "sonnet", "opus").
        effort:
            Optional effort level ("low"|"medium"|"high"|"max").
        max_turns:
            Maximum number of tool-use turns.

        Returns
        -------
        ToolUseResult
            Contains result_text, parsed_json (if parseable), exit_code,
            raw_stdout, raw_stderr.
        """
        argv = [
            _resolve_claude_binary(), "-p",
            "--model", model,
            "--max-turns", str(max_turns),
            "--output-format", "json",
        ]
        if effort is not None:
            argv += ["--effort", effort]

        result = subprocess_util.run(argv, input=prompt)

        parsed_json: dict | None = None
        result_text = ""
        parse_error: str | None = None
        session_id: str | None = None

        if result.returncode == 0 and result.stdout:
            # Extract session_id and result_text from outer JSON first —
            # these must survive even if inner result parsing fails.
            try:
                outer = json.loads(result.stdout)
                session_id = outer.get("session_id") if isinstance(outer.get("session_id"), str) else None
                result_text = str(outer.get("result", "") or "")
            except json.JSONDecodeError:
                pass

            if session_id is None:
                log("claude", "session_id not found in claude output; session resume unavailable")

            try:
                parsed_json, _ = _parse_claude_json_wrapper(result.stdout)
            except (ValueError, json.JSONDecodeError) as exc:
                # Inner result is not parseable as JSON dict — that's fine
                # for implementers that return free text. session_id and
                # result_text are already captured above.
                parse_error = f"{type(exc).__name__}: {exc}"

        return ToolUseResult(
            result_text=result_text,
            parsed_json=parsed_json,
            exit_code=result.returncode,
            raw_stdout=result.stdout,
            raw_stderr=result.stderr + (f"\n[claude parse_error] {parse_error}" if parse_error else ""),
            session_id=session_id,
        )

    def dispatch_tool_use_resume(
        self,
        session_id: str,
        prompt: str,
        *,
        model: str,
        effort: str | None,
        max_turns: int,
    ) -> ToolUseResult:
        """Resume a previous claude session via --resume <session_id>.

        Parameters
        ----------
        session_id:
            Session ID from a prior dispatch_tool_use call.
        prompt:
            New prompt text piped via stdin to the resumed session.
        model:
            Model name (e.g. "sonnet", "opus").
        effort:
            Optional effort level ("low"|"medium"|"high"|"max").
        max_turns:
            Maximum number of tool-use turns.

        Returns
        -------
        ToolUseResult
            Contains result_text, parsed_json (if parseable), exit_code,
            raw_stdout, raw_stderr, and the new session_id (may be same or
            forked if claude creates a new session branch).
        """
        argv = [
            _resolve_claude_binary(), "-p",
            "--resume", session_id,
            "--model", model,
            "--max-turns", str(max_turns),
            "--output-format", "json",
        ]
        if effort is not None:
            argv += ["--effort", effort]

        result = subprocess_util.run(argv, input=prompt)

        parsed_json: dict | None = None
        result_text = ""
        parse_error: str | None = None
        new_session_id: str | None = None

        if result.returncode == 0 and result.stdout:
            try:
                parsed_json, new_session_id = _parse_claude_json_wrapper(result.stdout)
                outer = json.loads(result.stdout)
                result_text = outer.get("result", "") or ""
                if new_session_id is None:
                    log("claude", "session_id not found in resume output; session chain broken")
            except (ValueError, json.JSONDecodeError) as exc:
                parse_error = f"{type(exc).__name__}: {exc}"

        return ToolUseResult(
            result_text=result_text,
            parsed_json=parsed_json,
            exit_code=result.returncode,
            raw_stdout=result.stdout,
            raw_stderr=result.stderr + (f"\n[claude parse_error] {parse_error}" if parse_error else ""),
            session_id=new_session_id,
        )

    def dispatch_bulk(
        self,
        prompt: str,
        output_path: Path,
        *,
        model: str,
        effort: str | None,
    ) -> BulkResult:
        """Run claude -p in text output mode, write result to output_path.

        Parameters
        ----------
        prompt:
            Prompt text sent to claude via stdin.
        output_path:
            File path where the bulk output is written.
        model:
            Model name.
        effort:
            Optional effort level.

        Returns
        -------
        BulkResult
        """
        # Write prompt to a temp file (claude -p reads stdin when no file given)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(prompt)
            prompt_path = Path(f.name)

        try:
            argv = [
                "claude", "-p",
                "--model", model,
                "--max-turns", "1",
                "--output-format", "json",
            ]
            if effort is not None:
                argv += ["--effort", effort]

            result = subprocess_util.run(argv, input=prompt)

            # Extract result text from JSON wrapper
            stdout_text = ""
            if result.returncode == 0 and result.stdout:
                try:
                    outer = json.loads(result.stdout)
                    stdout_text = outer.get("result", "") or ""
                except json.JSONDecodeError:
                    stdout_text = result.stdout

            if stdout_text:
                output_path.write_text(stdout_text, encoding="utf-8")

        finally:
            prompt_path.unlink(missing_ok=True)

        return BulkResult(
            stdout=stdout_text,
            stderr=result.stderr,
            exit_code=result.returncode,
            output_path=output_path,
        )


# Satisfy the Backend Protocol at import time (structural check)
_: Backend = ClaudeBackend()  # type: ignore[assignment]
