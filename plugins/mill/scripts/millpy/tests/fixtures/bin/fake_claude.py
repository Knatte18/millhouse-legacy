#!/usr/bin/env python
"""
fake_claude.py — Test fixture standing in for the `claude` CLI.

Reads a canned response from an environment variable or a responses
directory, writes it to stdout as if the real Claude CLI had produced
it, and exits 0. Used by D.3's E2E dummy-task smoke and by any test
that needs a real-subprocess dispatch path without actually spawning
Claude.

Environment variables:
  MILL_FAKE_CLAUDE_RESPONSE           literal string written verbatim to stdout
  MILL_FAKE_CLAUDE_RESPONSES_DIR      directory containing canned response files.
                                      The file is selected by inspecting argv
                                      for --model and the caller's "role" hint
                                      (implementer vs reviewer).
  MILL_FAKE_CLAUDE_EXIT_CODE          override exit code (default 0)

Priority: MILL_FAKE_CLAUDE_RESPONSE wins over MILL_FAKE_CLAUDE_RESPONSES_DIR.

The real `claude -p --output-format json` wraps its result in
``{"result": "<text>", ...}``. This fixture wraps the canned response in
the same envelope so callers that go through
``millpy.backends.claude._parse_claude_json_wrapper`` see a realistic
shape. If the canned response is already a full JSON envelope (starts
with ``{"result"``), it's written verbatim.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _select_response_file(responses_dir: Path, argv: list[str]) -> Path | None:
    """Pick a response file by scanning argv for hints.

    Priority order for filename matching:
    1. "<model>-<phase>-r<round>.json" (reviewer with phase+round context)
    2. "<model>.json" (generic per-model response)
    3. "implementer.json" (generic implementer response)
    4. "default.json" (catch-all)
    """
    model = None
    for i, arg in enumerate(argv):
        if arg == "--model" and i + 1 < len(argv):
            model = argv[i + 1]
            break

    candidates: list[str] = []
    if model:
        candidates.append(f"{model}.json")
    candidates.extend(["implementer.json", "default.json"])

    for name in candidates:
        path = responses_dir / name
        if path.exists():
            return path
    return None


def _wrap_as_claude_envelope(response_text: str) -> str:
    """Wrap a raw response string as the claude -p JSON envelope."""
    stripped = response_text.strip()
    if stripped.startswith('{"result"'):
        return response_text
    envelope = {"result": response_text, "cost": 0, "duration_ms": 0}
    return json.dumps(envelope)


def main(argv: list[str]) -> int:
    exit_code = int(os.environ.get("MILL_FAKE_CLAUDE_EXIT_CODE", "0"))

    canned = os.environ.get("MILL_FAKE_CLAUDE_RESPONSE")
    if canned is not None:
        sys.stdout.write(_wrap_as_claude_envelope(canned))
        sys.stdout.flush()
        return exit_code

    responses_dir_str = os.environ.get("MILL_FAKE_CLAUDE_RESPONSES_DIR")
    if responses_dir_str:
        responses_dir = Path(responses_dir_str)
        response_file = _select_response_file(responses_dir, argv)
        if response_file is None:
            print(
                f"[fake_claude] no matching response file in {responses_dir}",
                file=sys.stderr,
            )
            return 1
        text = response_file.read_text(encoding="utf-8")
        sys.stdout.write(_wrap_as_claude_envelope(text))
        sys.stdout.flush()
        return exit_code

    print(
        "[fake_claude] neither MILL_FAKE_CLAUDE_RESPONSE nor MILL_FAKE_CLAUDE_RESPONSES_DIR set",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
