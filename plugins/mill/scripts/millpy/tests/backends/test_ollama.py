"""
test_ollama.py — Tests for millpy.backends.ollama pure helpers.

Only compute_num_ctx and strip_think_blocks are unit-tested.
HTTP code paths are NOT tested (covered by live smoke if ollama is available).
"""
from __future__ import annotations

import pytest

from millpy.backends.ollama import compute_num_ctx, strip_think_blocks


class TestComputeNumCtx:
    def test_small_prompt_rounds_up(self):
        # 1000 chars → 1000//3 + 4096 = 333 + 4096 = 4429 → rounded to 8192
        result = compute_num_ctx(1000)
        assert result == 8192

    def test_caps_at_96000(self):
        # Need prompt_chars large enough that estimate > 96000
        # 96000 = prompt_chars//3 + 4096 → prompt_chars > (96000-4096)*3 = 275712
        result = compute_num_ctx(300000)
        assert result == 96000

    def test_zero_chars_returns_minimum(self):
        result = compute_num_ctx(0)
        # 0//3 + 4096 = 4096 → candidate = max(8192, 4096) = 8192
        assert result == 8192

    def test_medium_prompt_rounds_correctly(self):
        # 60000 chars → 60000//3 + 4096 = 20000 + 4096 = 24096
        # rounded to next multiple of 4096: ceil(24096/4096) * 4096 = 6*4096 = 24576
        result = compute_num_ctx(60000)
        assert result % 4096 == 0
        assert result >= 24096

    def test_result_always_multiple_of_4096(self):
        for chars in [0, 100, 1000, 10000, 50000, 150000]:
            assert compute_num_ctx(chars) % 4096 == 0


class TestStripThinkBlocks:
    def test_removes_think_block(self):
        text = "before <think>secret</think> after"
        result = strip_think_blocks(text)
        assert "secret" not in result
        assert "before" in result
        assert "after" in result

    def test_multiline_think_block(self):
        text = "intro\n<think>\n  content\n  more\n</think>\nconclusion"
        result = strip_think_blocks(text)
        assert "content" not in result
        assert "more" not in result
        assert "intro" in result
        assert "conclusion" in result

    def test_no_think_block_unchanged(self):
        text = "This text has no think block."
        result = strip_think_blocks(text)
        assert "no think block" in result

    def test_multiple_think_blocks(self):
        text = "<think>a</think> middle <think>b</think>"
        result = strip_think_blocks(text)
        assert "a" not in result
        assert "b" not in result
        assert "middle" in result

    def test_empty_string(self):
        result = strip_think_blocks("")
        assert result == ""

    def test_think_block_at_start(self):
        text = "<think>hidden</think>visible"
        result = strip_think_blocks(text)
        assert "hidden" not in result
        assert "visible" in result
