"""
reviewers/workers.py — WORKERS registry: atomic worker configurations.

Each entry is a named (provider, model, effort, dispatch_mode) tuple.
Haiku is deliberately absent — not strong enough for reviews.

Model-name verification: spawn-agent.ps1 maps:
  'gemini-3-pro'   → 'gemini-3-pro-preview'   (native Gemini model name)
  'gemini-flash'   → 'gemini-3-flash-preview'  (native Gemini model name)
So the WORKERS use the -preview suffix strings that the Gemini CLI accepts.

No cross-import with definitions.py. Registry validation lives in __init__.py.
"""
from __future__ import annotations

from millpy.reviewers.base import Worker

WORKERS: dict[str, Worker] = {
    "sonnet": Worker(
        provider="claude",
        model="sonnet",
    ),
    "sonnetmax": Worker(
        provider="claude",
        model="sonnet",
        effort="max",
    ),
    "opus": Worker(
        provider="claude",
        model="opus",
    ),
    "opusmax": Worker(
        provider="claude",
        model="opus",
        effort="max",
    ),
    "g3flash": Worker(
        provider="gemini",
        model="gemini-3-flash-preview",
    ),
    "g3pro": Worker(
        provider="gemini",
        model="gemini-3-pro-preview",
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
