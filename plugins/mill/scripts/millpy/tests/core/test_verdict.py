"""Tests for millpy.core.verdict — fence-stripping helper and multi-format extraction.

Covers:
- parse_verdict_line: JSON line with optional markdown fence wrapping
- extract_verdict_from_text: multi-format extraction (frontmatter → JSON → VERDICT: prefix → UNKNOWN)

Live repros driving the multi-format extraction:
- Discussion review round 1 (2026-04-15): worker emitted JSON wrapped in single
  backticks, engine returned verdict=UNKNOWN. File:
  _millhouse/task/reviews/20260415-081248-discussion-review-r1.md
- Discussion review round 2 (2026-04-15): worker emitted clean JSON, engine
  still returned verdict=UNKNOWN. File:
  _millhouse/task/reviews/20260415-083554-discussion-review-r2.md
"""
from __future__ import annotations

import pytest

from millpy.core.verdict import (
    VERDICT_ERROR,
    VerdictParseError,
    extract_verdict_from_text,
    parse_verdict_line,
)


# ---------------------------------------------------------------
# parse_verdict_line
# ---------------------------------------------------------------


def test_parse_verdict_line_clean_json():
    raw = '{"verdict": "APPROVE", "review_file": "/tmp/x.md"}'
    assert parse_verdict_line(raw) == {"verdict": "APPROVE", "review_file": "/tmp/x.md"}


def test_parse_verdict_line_triple_backtick():
    raw = '```\n{"verdict": "APPROVE"}\n```'
    assert parse_verdict_line(raw) == {"verdict": "APPROVE"}


def test_parse_verdict_line_triple_backtick_with_language_marker():
    raw = '```json\n{"verdict": "APPROVE"}\n```'
    assert parse_verdict_line(raw) == {"verdict": "APPROVE"}


def test_parse_verdict_line_single_backtick():
    raw = '`{"verdict": "APPROVE"}`'
    assert parse_verdict_line(raw) == {"verdict": "APPROVE"}


def test_parse_verdict_line_leading_and_trailing_whitespace():
    raw = '   {"verdict": "APPROVE"}   \n'
    assert parse_verdict_line(raw) == {"verdict": "APPROVE"}


def test_parse_verdict_line_fence_plus_surrounding_whitespace():
    raw = '  `{"verdict": "APPROVE"}`  \n'
    assert parse_verdict_line(raw) == {"verdict": "APPROVE"}


def test_parse_verdict_line_invalid_json_raises():
    with pytest.raises(VerdictParseError, match="not json"):
        parse_verdict_line("not json")


def test_parse_verdict_line_json_array_raises():
    with pytest.raises(VerdictParseError, match="dict|object"):
        parse_verdict_line('["APPROVE"]')


def test_parse_verdict_line_round1_live_repro():
    """Live repro from discussion review round 1 — backtick-wrapped JSON."""
    raw = '`{"verdict": "GAPS_FOUND", "review_file": "C:/Code/millhouse.worktrees/stabilization-bundle/_millhouse/task/reviews/20260415-081248-discussion-review-r1.md"}`'
    result = parse_verdict_line(raw)
    assert result["verdict"] == "GAPS_FOUND"
    assert "discussion-review-r1.md" in result["review_file"]


# ---------------------------------------------------------------
# extract_verdict_from_text — frontmatter path (highest priority)
# ---------------------------------------------------------------


def test_extract_frontmatter_simple():
    text = "---\nverdict: APPROVE\ntimestamp: 20260415-120000\n---\n\n# Review body\n"
    assert extract_verdict_from_text(text) == "APPROVE"


def test_extract_frontmatter_lowercase_key():
    text = "---\nverdict: GAPS_FOUND\n---\n\nbody\n"
    assert extract_verdict_from_text(text) == "GAPS_FOUND"


def test_extract_frontmatter_double_quoted_value():
    text = '---\nverdict: "GAPS_FOUND"\n---\n\nbody\n'
    assert extract_verdict_from_text(text) == "GAPS_FOUND"


def test_extract_frontmatter_single_quoted_value():
    text = "---\nverdict: 'REQUEST_CHANGES'\n---\n\nbody\n"
    assert extract_verdict_from_text(text) == "REQUEST_CHANGES"


def test_extract_frontmatter_case_insensitive_key():
    text = "---\nVERDICT: APPROVE\n---\n\nbody\n"
    assert extract_verdict_from_text(text) == "APPROVE"


# ---------------------------------------------------------------
# extract_verdict_from_text — JSON last-line path
# ---------------------------------------------------------------


def test_extract_json_last_line():
    text = 'some review narrative\n\n{"verdict": "REQUEST_CHANGES", "review_file": "/tmp/x.md"}'
    assert extract_verdict_from_text(text) == "REQUEST_CHANGES"


def test_extract_fence_wrapped_json_last_line():
    """Round-1 live repro format: worker emitted backtick-wrapped JSON."""
    text = 'some review text\n\n`{"verdict": "GAPS_FOUND", "review_file": "/tmp/x.md"}`'
    assert extract_verdict_from_text(text) == "GAPS_FOUND"


def test_extract_triple_backtick_fenced_json_last_line():
    text = 'review body\n\n```json\n{"verdict": "APPROVE"}\n```'
    assert extract_verdict_from_text(text) == "APPROVE"


def test_extract_clean_json_last_line_after_trailing_newlines():
    """Round-2 live repro: clean JSON as the only non-empty line."""
    text = '{"verdict": "APPROVE", "review_file": "c:\\\\Code\\\\mh\\\\_millhouse\\\\task\\\\reviews\\\\20260415-083554-discussion-review-r2.md"}\n'
    assert extract_verdict_from_text(text) == "APPROVE"


# ---------------------------------------------------------------
# extract_verdict_from_text — VERDICT: prefix (backward-compat)
# ---------------------------------------------------------------


def test_extract_verdict_prefix_backward_compat():
    text = "body\nVERDICT: APPROVE\n"
    assert extract_verdict_from_text(text) == "APPROVE"


# ---------------------------------------------------------------
# extract_verdict_from_text — precedence + fallback
# ---------------------------------------------------------------


def test_extract_frontmatter_wins_over_json_last_line():
    """Frontmatter has highest priority; JSON last line ignored when both present."""
    text = '---\nverdict: GAPS_FOUND\n---\n\nbody\n\n{"verdict": "APPROVE"}'
    assert extract_verdict_from_text(text) == "GAPS_FOUND"


def test_extract_no_recognizable_format_returns_error():
    # Non-empty text with no verdict signal → ERROR (not UNKNOWN).
    # UNKNOWN is reserved for empty/whitespace-only input.
    text = "plain text with no verdict at all"
    assert extract_verdict_from_text(text) == VERDICT_ERROR


def test_extract_empty_text_returns_unknown():
    assert extract_verdict_from_text("") == "UNKNOWN"


def test_extract_whitespace_only_returns_unknown():
    assert extract_verdict_from_text("   \n\n  \n") == "UNKNOWN"


def test_extract_invalid_json_falls_back_to_verdict_prefix():
    text = "body\nVERDICT: APPROVE\n{malformed json last"
    assert extract_verdict_from_text(text) == "APPROVE"


# ---------------------------------------------------------------
# extract_verdict_from_text — body-grep tier (tier 4)
# ---------------------------------------------------------------


def test_body_grep_approve():
    text = "Some review prose.\n\nVerdict: APPROVE\n\nMore prose."
    assert extract_verdict_from_text(text) == "APPROVE"


def test_body_grep_bold_markdown():
    text = "Review body.\n\n**Verdict:** REQUEST_CHANGES\n"
    assert extract_verdict_from_text(text) == "REQUEST_CHANGES"


def test_body_grep_heading():
    text = "## Summary\n\nSome text.\n\n### Verdict — APPROVE\n"
    assert extract_verdict_from_text(text) == "APPROVE"


def test_body_grep_case_insensitive():
    text = "verdict: approve\n"
    assert extract_verdict_from_text(text) == "APPROVE"


# ---------------------------------------------------------------
# extract_verdict_from_text — ERROR / UNKNOWN sentinels
# ---------------------------------------------------------------


def test_error_sentinel_on_unparseable_non_empty():
    text = "This is a review with no verdict declaration anywhere in it."
    assert extract_verdict_from_text(text) == VERDICT_ERROR


def test_unknown_sentinel_on_empty_input():
    assert extract_verdict_from_text("") == "UNKNOWN"


def test_whitespace_returns_unknown():
    assert extract_verdict_from_text("   \n\n  ") == "UNKNOWN"
