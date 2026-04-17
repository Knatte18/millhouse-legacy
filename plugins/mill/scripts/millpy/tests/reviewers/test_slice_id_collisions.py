"""Filename-distinctness tests for `_make_review_filename`.

Parallel-fan-out callers (per-card code review, per-batch plan review) MUST
pass a non-empty `slice_id` to keep concurrent filenames distinct. When
`slice_id` is None on both calls with the same ts + reviewer_name + round,
the filenames are EQUAL — this is the documented collision path that callers
are responsible for avoiding.

See `reviewers/engine.py::_make_review_filename`.
"""
from __future__ import annotations

from millpy.reviewers.engine import _make_review_filename


TS = "20260417-020304"
REVIEWER = "g25flash"
ROUND = 1


def test_distinct_slice_ids_produce_distinct_filenames():
    """Three parallel workers w/ different slice_ids → three distinct filenames."""
    a = _make_review_filename(TS, REVIEWER, "card-1", ROUND)
    b = _make_review_filename(TS, REVIEWER, "card-2", ROUND)
    c = _make_review_filename(TS, REVIEWER, "card-3", ROUND)
    assert a != b
    assert b != c
    assert a != c
    assert a == f"{TS}-{REVIEWER}-card-1-r{ROUND}.md"


def test_same_slice_id_different_rounds_distinct():
    """Same slice_id, different round → `-r{round}` suffix differentiates."""
    r1 = _make_review_filename(TS, REVIEWER, "card-1", 1)
    r2 = _make_review_filename(TS, REVIEWER, "card-1", 2)
    assert r1 != r2
    assert r1.endswith("-r1.md")
    assert r2.endswith("-r2.md")


def test_none_slice_id_collides_with_itself():
    """slice_id=None on both → filenames are EQUAL.

    This is the expected collision — callers in parallel-fan-out contexts
    (per-card review, per-batch review) are responsible for passing a
    non-empty slice_id to avoid this. Single-slice callers pass None and
    accept the shorter filename (they have no fan-out to collide with).
    """
    a = _make_review_filename(TS, REVIEWER, None, ROUND)
    b = _make_review_filename(TS, REVIEWER, None, ROUND)
    assert a == b  # expected collision — documented behavior
    assert a == f"{TS}-{REVIEWER}-r{ROUND}.md"
    assert "None" not in a  # never embed the string "None" into filenames


def test_none_slice_id_vs_string_slice_id_differ():
    """slice_id=None produces shorter filename than slice_id="foo"."""
    with_id = _make_review_filename(TS, REVIEWER, "foo", ROUND)
    without = _make_review_filename(TS, REVIEWER, None, ROUND)
    assert with_id != without
    assert "foo" in with_id
    assert "foo" not in without


def test_empty_string_slice_id_treated_as_none():
    """Empty-string slice_id is falsy → same filename as None."""
    empty = _make_review_filename(TS, REVIEWER, "", ROUND)
    none_ = _make_review_filename(TS, REVIEWER, None, ROUND)
    assert empty == none_
