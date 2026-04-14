"""
backends/ollama.py — Ollama HTTP backend for millpy.

Ported from plugins/mill/scripts/spawn_agent.py (the existing file is a
reference — this is a clean rewrite into the Backend Protocol shape).

Uses urllib.request (stdlib only). No requests library.

Pure helpers (unit-tested):
  compute_num_ctx(prompt_chars) — KV-cache sizing
  strip_think_blocks(text)      — remove <think>...</think> regions

HTTP code path is NOT unit-tested (covered by live smoke if ollama is available).
All subprocess calls (for the bash tool in TOOL_DISPATCH) go through
core.subprocess_util.run — no bare subprocess.run.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import urllib.error
import urllib.request
from pathlib import Path

from millpy.backends.base import Backend, BulkResult, ToolUseResult
from millpy.core import subprocess_util
from millpy.core.log_util import log


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "http://localhost:11434")

# Model → (think-enabled, aliases) map.
# think=True routes reasoning into a separate `thinking` field so the
# `response` field contains only the final answer.
OLLAMA_MODELS: dict[str, tuple[bool, list[str]]] = {
    "glm-4.7-flash:latest": (False, ["glm-flash", "ollama-glm-flash"]),
    "qwen3:30b-thinking": (True, ["qwenthinker", "ollama-qwen-thinker"]),
}

# GLM-4.7-Flash stability ceiling (tokens). Anything larger degrades.
_MAX_NUM_CTX: int = 96000

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

# Tool output truncation threshold
_TOOL_OUTPUT_MAX_CHARS: int = 16000


# ---------------------------------------------------------------------------
# Pure helpers — unit-tested
# ---------------------------------------------------------------------------

def compute_num_ctx(prompt_chars: int) -> int:
    """Size the KV cache to the prompt plus a 4 KiB response budget.

    Rounds up to the nearest 4096 and caps at _MAX_NUM_CTX (96k tokens,
    the GLM-4.7-Flash stability ceiling). Chars→tokens at ~3 chars/token is
    deliberately pessimistic so that English text has headroom.

    Parameters
    ----------
    prompt_chars:
        Character count of the prompt string.

    Returns
    -------
    int
        Context window size in tokens, aligned to 4096, capped at 96000.
    """
    estimate = prompt_chars // 3 + 4096
    candidate = max(8192, estimate)
    candidate = ((candidate + 4095) // 4096) * 4096
    return min(candidate, _MAX_NUM_CTX)


def strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> CoT blocks emitted by reasoning models.

    Handles multiline think blocks. The stripped text is NOT stripped of
    surrounding whitespace — that is the caller's job if needed.

    Parameters
    ----------
    text:
        Raw model output that may contain think blocks.

    Returns
    -------
    str
        Text with all <think>...</think> regions removed.
    """
    return _THINK_BLOCK_RE.sub("", text)


# ---------------------------------------------------------------------------
# Tool helpers (for TOOL_DISPATCH)
# ---------------------------------------------------------------------------

def _truncate_tool_output(text: str) -> str:
    """Truncate tool output to _TOOL_OUTPUT_MAX_CHARS."""
    if len(text) <= _TOOL_OUTPUT_MAX_CHARS:
        return text
    head = _TOOL_OUTPUT_MAX_CHARS // 2
    tail = _TOOL_OUTPUT_MAX_CHARS - head - 100
    return text[:head] + f"\n... [truncated {len(text) - head - tail} chars] ...\n" + text[-tail:]


def _tool_read_file(workspace: str, args: dict) -> str:
    path = args.get("path", "")
    if not path:
        return "ERROR: path is required"
    abs_path = path if os.path.isabs(path) else os.path.join(workspace, path)
    if not os.path.exists(abs_path):
        return f"ERROR: file not found: {path}"
    if os.path.isdir(abs_path):
        return f"ERROR: path is a directory: {path}"
    offset = int(args.get("offset", 1))
    limit = int(args.get("limit", 2000))
    try:
        with open(abs_path, encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except Exception as exc:
        return f"ERROR: {exc}"
    start = max(0, offset - 1)
    end = min(len(all_lines), start + limit)
    numbered = [f"{i + 1:6d}\t{all_lines[i].rstrip()}" for i in range(start, end)]
    return _truncate_tool_output("\n".join(numbered))


def _tool_grep(workspace: str, args: dict) -> str:
    pattern = args.get("pattern", "")
    if not pattern:
        return "ERROR: pattern is required"
    path = args.get("path", workspace)
    if not os.path.isabs(path):
        path = os.path.join(workspace, path)
    glob_filter = args.get("glob", "")
    rg = shutil.which("rg")
    if rg:
        cmd = [rg, "--line-number", "--no-heading", "--color", "never", pattern, path]
        if glob_filter:
            cmd += ["--glob", glob_filter]
    else:
        if glob_filter:
            return f"ERROR: glob filter requires ripgrep; install rg or omit glob (got: {glob_filter})"
        cmd = ["grep", "-rn", pattern, path]
    result = subprocess_util.run(cmd, cwd=workspace, timeout=30)
    output = result.stdout.strip()
    return _truncate_tool_output(output) if output else "(no matches)"


def _tool_bash(workspace: str, args: dict) -> str:
    command = args.get("command", "")
    if not command:
        return "ERROR: command is required"
    shell = shutil.which("bash") or shutil.which("bash.exe")
    if shell:
        argv = [shell, "-c", command]
    else:
        # Fallback: let subprocess_util run via shell=False (may not work on all cmds)
        argv = command.split()
    result = subprocess_util.run(argv, cwd=workspace, timeout=60)
    output_parts = []
    if result.stdout:
        output_parts.append(result.stdout)
    if result.stderr:
        output_parts.append(f"\n--- stderr ---\n{result.stderr}")
    if result.returncode != 0:
        output_parts.append(f"\n--- exit code: {result.returncode} ---")
    combined = "".join(output_parts).strip() or "(no output)"
    return _truncate_tool_output(combined)


TOOL_DISPATCH: dict[str, object] = {
    "read_file": _tool_read_file,
    "grep": _tool_grep,
    "bash": _tool_bash,
}

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the workspace. Returns the file contents with line numbers prefixed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Workspace-relative or absolute path"},
                    "offset": {"type": "integer", "description": "1-indexed starting line (optional)"},
                    "limit": {"type": "integer", "description": "Number of lines to read (optional, default 2000)"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search files using ripgrep. Returns matching lines with file:line prefixes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern"},
                    "path": {"type": "string", "description": "File or directory to search (optional)"},
                    "glob": {"type": "string", "description": "File glob filter e.g. '*.py' (optional)"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run"},
                },
                "required": ["command"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _ollama_generate(
    model: str,
    prompt: str,
    timeout: int,
    think: bool,
) -> tuple[str, int]:
    """POST to /api/generate and return (response_text, num_ctx)."""
    num_ctx = compute_num_ctx(len(prompt))
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": think,
        "options": {"num_ctx": num_ctx},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read())
    response_text = strip_think_blocks(payload.get("response", ""))
    return response_text, num_ctx


def _ollama_chat(
    model: str,
    messages: list,
    tools: list,
    num_ctx: int,
    timeout: int,
    think: bool,
) -> dict:
    """POST to /api/chat and return the parsed response dict."""
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "think": think,
        "tools": tools,
        "options": {"num_ctx": num_ctx},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _resolve_model(model: str) -> tuple[str, bool] | None:
    """Resolve a model string to (tag, think_enabled).

    Checks direct model tag first, then alias lists.
    Returns None if not found.
    """
    if model in OLLAMA_MODELS:
        think, _aliases = OLLAMA_MODELS[model]
        return model, think
    for tag, (think, aliases) in OLLAMA_MODELS.items():
        if model in aliases:
            return tag, think
    return None


# ---------------------------------------------------------------------------
# OllamaBackend
# ---------------------------------------------------------------------------

class OllamaBackend:
    """Ollama HTTP backend implementing the Backend Protocol.

    Uses urllib.request (stdlib). No third-party dependencies.
    """

    def __init__(self, timeout: int = 1800) -> None:
        """Initialize the backend.

        Parameters
        ----------
        timeout:
            HTTP request timeout in seconds (default 1800 = 30 min).
        """
        self.timeout = timeout

    def dispatch_bulk(
        self,
        prompt: str,
        output_path: Path,
        *,
        model: str,
        effort: str | None,
    ) -> BulkResult:
        """POST to Ollama /api/generate, strip think blocks, write output.

        Parameters
        ----------
        prompt:
            Prompt text sent to the model.
        output_path:
            File path where the response is written.
        model:
            Ollama model name or alias.
        effort:
            Ignored — Ollama does not support an effort parameter.

        Returns
        -------
        BulkResult
        """
        resolved = _resolve_model(model)
        if resolved is None:
            tag = model
            think = False
        else:
            tag, think = resolved

        log("ollama", f"dispatch_bulk model={tag} think={think} prompt_chars={len(prompt)}")

        try:
            response_text, num_ctx = _ollama_generate(tag, prompt, self.timeout, think)
        except urllib.error.URLError as exc:
            log("ollama", f"request failed: {exc}")
            return BulkResult(
                stdout="",
                stderr=str(exc),
                exit_code=12,
                output_path=output_path,
            )

        log("ollama", f"num_ctx={num_ctx} response_chars={len(response_text)}")

        if response_text:
            output_path.write_text(response_text, encoding="utf-8")

        return BulkResult(
            stdout=response_text,
            stderr="",
            exit_code=0,
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
        """POST to Ollama /api/chat with tool-use loop.

        Runs up to max_turns iterations. Each tool call is dispatched via
        TOOL_DISPATCH. Returns ToolUseResult with the final model text.

        Parameters
        ----------
        prompt:
            User prompt text.
        model:
            Ollama model name or alias.
        effort:
            Ignored — Ollama does not support an effort parameter.
        max_turns:
            Maximum number of tool-use turns.

        Returns
        -------
        ToolUseResult
        """
        resolved = _resolve_model(model)
        if resolved is None:
            tag = model
            think = False
        else:
            tag, think = resolved

        workspace = str(Path.cwd())
        num_ctx = compute_num_ctx(len(prompt) + 8192)

        log("ollama", f"dispatch_tool_use model={tag} think={think} num_ctx={num_ctx} max_turns={max_turns}")

        messages: list = [
            {
                "role": "system",
                "content": (
                    "You are an independent code reviewer. Use the provided tools "
                    "(read_file, grep, bash) to gather context. When you have enough "
                    "information, output your review as markdown with a final line "
                    "`VERDICT: APPROVE` or `VERDICT: REQUEST_CHANGES`. Do not call "
                    "tools after producing the VERDICT line."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        final_text = ""
        for turn in range(1, max_turns + 1):
            try:
                response = _ollama_chat(tag, messages, TOOL_SCHEMAS, num_ctx, self.timeout, think)
            except urllib.error.URLError as exc:
                log("ollama", f"request failed on turn {turn}: {exc}")
                return ToolUseResult(
                    result_text="",
                    parsed_json=None,
                    exit_code=12,
                    raw_stdout="",
                    raw_stderr=str(exc),
                )

            msg = response.get("message", {})
            content = msg.get("content", "") or ""
            tool_calls = msg.get("tool_calls") or []
            log("ollama", f"turn {turn}: content_chars={len(content)} tool_calls={len(tool_calls)}")
            messages.append(msg)

            if not tool_calls:
                final_text = content
                break

            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                tc_args = fn.get("arguments") or {}
                if isinstance(tc_args, str):
                    try:
                        tc_args = json.loads(tc_args)
                    except json.JSONDecodeError:
                        tc_args = {}

                handler = TOOL_DISPATCH.get(name)
                if handler is None:
                    tool_result = f"ERROR: unknown tool {name}"
                else:
                    try:
                        tool_result = handler(workspace, tc_args)  # type: ignore[operator]
                    except Exception as exc:
                        tool_result = f"ERROR: tool {name} raised {type(exc).__name__}: {exc}"

                log("ollama", f"  tool {name}({json.dumps(tc_args)[:120]}) → {len(tool_result)} chars")
                messages.append({
                    "role": "tool",
                    "name": name,
                    "content": tool_result,
                })
        else:
            log("ollama", f"hit max_turns={max_turns} without final answer")
            if not final_text and messages:
                final_text = messages[-1].get("content", "") if messages else ""

        return ToolUseResult(
            result_text=final_text,
            parsed_json=None,
            exit_code=0,
            raw_stdout=final_text,
            raw_stderr="",
        )


# Satisfy the Backend Protocol at import time (structural check)
_: Backend = OllamaBackend()  # type: ignore[assignment]
