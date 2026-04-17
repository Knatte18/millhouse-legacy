"""
reviewers/workers.py — WORKERS registry: atomic worker configurations.

Each entry is a named (provider, model, effort, dispatch_mode) tuple.
Haiku is available but not a default reviewer choice — previously deemed
too weak; kept for experimental per-card runs where low token cost matters.

Model names are passed verbatim to the Gemini CLI via `gemini --model <name>`:
  - gemini-3 variants use the `-preview` suffix (gemini-3-pro-preview, gemini-3-flash-preview)
  - gemini-2.5 variants are GA and use the plain name (gemini-2.5-pro, gemini-2.5-flash)

Claude workers use max_turns=500 (not the Worker default of 30). Holistic tool-use
reviews on multi-file artifacts legitimately need 50-150 turns, and the Claude CLI
has a known subprocess-hang bug that kicks in after ~15-20 min regardless of
max_turns — so the cap is set well above realistic need and the real reliability
ceiling is documented separately. See plugins/mill/doc/providers/claude-cli-limits.md.

No cross-import with definitions.py. Registry validation lives in __init__.py.
"""
from __future__ import annotations

from millpy.reviewers.base import Worker

WORKERS: dict[str, Worker] = {
    "haiku": Worker(
        provider="claude",
        model="haiku",
        max_turns=500,
    ),
    "sonnet": Worker(
        provider="claude",
        model="sonnet",
        max_turns=500,
    ),
    "sonnetmax": Worker(
        provider="claude",
        model="sonnet",
        effort="max",
        max_turns=500,
    ),
    "opus": Worker(
        provider="claude",
        model="opus",
        max_turns=500,
    ),
    "opusmax": Worker(
        provider="claude",
        model="opus",
        effort="max",
        max_turns=500,
    ),
    "g3flash": Worker(
        provider="gemini",
        model="gemini-3-flash-preview",
    ),
    "g3pro": Worker(
        provider="gemini",
        model="gemini-3-pro-preview",
    ),
    "g25flash": Worker(
        provider="gemini",
        model="gemini-2.5-flash",
    ),
    "g25pro": Worker(
        provider="gemini",
        model="gemini-2.5-pro",
    ),
    "glmflash": Worker(
        provider="ollama",
        model="glm-4.7-flash:latest",
    ),
    "qwenthinker": Worker(
        provider="ollama",
        model="qwen3:30b-thinking",
        extras={"think": True},
    ),
}
