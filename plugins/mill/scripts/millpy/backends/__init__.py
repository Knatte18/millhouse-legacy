"""
backends/__init__.py — BACKENDS registry for millpy.

Imports all three concrete backend implementations and exposes a dict-based
registry. Registry cross-validation lives in reviewers/__init__.py.
"""
from __future__ import annotations

from millpy.backends.base import Backend
from millpy.backends.claude import ClaudeBackend
from millpy.backends.gemini import GeminiBackend
from millpy.backends.ollama import OllamaBackend

BACKENDS: dict[str, Backend] = {
    "claude": ClaudeBackend(),
    "gemini": GeminiBackend(),
    "ollama": OllamaBackend(),
}

__all__ = ["BACKENDS", "Backend", "ClaudeBackend", "GeminiBackend", "OllamaBackend"]
