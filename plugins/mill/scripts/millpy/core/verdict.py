"""
verdict.py — Shared verdict parsing helpers for millpy.

Two public functions:

- ``parse_verdict_line(raw)`` — fence-stripping + JSON parse of a single
  verdict line produced by a worker. Used at entrypoint level
  (spawn_agent.py, spawn_reviewer.py) to decode the child process's
  stdout verdict line.

- ``extract_verdict_from_text(text)`` — multi-format extraction of a
  verdict string from arbitrary text. Recognizes (in priority order):
  (1) YAML frontmatter ``verdict:`` field, (2) JSON object as the last
  non-empty line (with optional backtick fences), (3) ``VERDICT:``
  prefix line (backward-compat). Falls back to ``"UNKNOWN"`` when no
  recognizable format is present. Used by the reviewer engine's
  ``_extract_verdict`` single-worker and ensemble paths.

Historical context — live repros driving the multi-format design:

  Discussion review round 1 (2026-04-15): the sonnet worker emitted its
  final JSON line wrapped in single backticks. The engine's verdict
  return path captured the raw wrapped string, tried to parse it as a
  JSON verdict envelope, failed, and returned ``verdict: UNKNOWN`` to
  the orchestrator even though the review file itself was written
  correctly. Review file:
  ``_millhouse/task/reviews/20260415-081248-discussion-review-r1.md``

  Discussion review round 2 (2026-04-15): the worker emitted clean JSON
  with no fence wrapping at all. The engine STILL returned
  ``verdict: UNKNOWN``. Investigation found duplicate copies of
  ``_extract_verdict`` in ``reviewers/base.py`` and ``reviewers/ensemble.py``,
  both scanning for a literal ``VERDICT:`` prefix line — neither JSON
  nor YAML frontmatter matched, so both paths always defaulted to
  ``UNKNOWN``. Review file:
  ``_millhouse/task/reviews/20260415-083554-discussion-review-r2.md``

Both failure modes are resolved by routing through
``extract_verdict_from_text``, which recognizes frontmatter, fence-wrapped
JSON, clean JSON, AND the legacy ``VERDICT:`` prefix.
"""
from __future__ import annotations

import json
import re
from typing import Any


class VerdictParseError(ValueError):
    """Raised when parse_verdict_line cannot parse its input as a JSON object."""


def _strip_fences(text: str) -> str:
    """Strip markdown code fences from text. Supports triple-backtick and single-backtick."""
    stripped = text.strip()

    if stripped.startswith("```") and stripped.endswith("```"):
        inner = stripped[3:-3]
        if "\n" in inner:
            first_line, rest = inner.split("\n", 1)
            if first_line.strip() and not first_line.strip().startswith("{"):
                inner = rest
        return inner.strip()

    if stripped.startswith("`") and stripped.endswith("`") and len(stripped) >= 2:
        return stripped[1:-1].strip()

    return stripped


def parse_verdict_line(raw: str) -> dict[str, Any]:
    """Parse a verdict JSON line, stripping optional markdown fences first.

    Parameters
    ----------
    raw:
        A string containing a JSON object, optionally wrapped in
        triple-backtick or single-backtick markdown fences, optionally
        with a language marker after the opening triple-backtick.

    Returns
    -------
    dict
        The parsed JSON object.

    Raises
    ------
    VerdictParseError
        If the stripped content is not valid JSON, or if it parses to a
        value other than a dict (e.g. array, scalar).
    """
    stripped = _strip_fences(raw)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise VerdictParseError(
            f"verdict line is not valid JSON: {raw!r} (error: {exc})"
        ) from exc
    if not isinstance(parsed, dict):
        raise VerdictParseError(
            f"verdict line must parse to a JSON object, got {type(parsed).__name__}: {raw!r}"
        )
    return parsed


_FRONTMATTER_VERDICT_PATTERN = re.compile(
    r"^\s*verdict\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)


def _extract_from_frontmatter(text: str) -> str | None:
    """Return the `verdict:` value from YAML frontmatter, or None if not present."""
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return None

    lines = stripped.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            for frontmatter_line in lines[1:i]:
                match = _FRONTMATTER_VERDICT_PATTERN.match(frontmatter_line)
                if match:
                    return _clean_value(match.group(1))
            return None
    return None


def _clean_value(value: str) -> str:
    """Strip surrounding quotes and trailing punctuation from a verdict value."""
    value = value.strip()
    if len(value) >= 2:
        if (value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'"):
            value = value[1:-1]
    value = value.rstrip(".,;")
    return value


_TRAILING_TRIPLE_FENCE_PATTERN = re.compile(
    r"```[a-zA-Z0-9_-]*\s*\n(.*?)\n\s*```\s*\Z",
    re.DOTALL,
)


def _extract_from_json_last_line(text: str) -> str | None:
    """Return the `verdict` field from the last JSON payload in the text.

    Recognizes three shapes at the end of the text:
    - A single line containing ``{...}`` (clean JSON as last line)
    - A single line wrapped in single backticks (``` `{...}` ``)
    - A multi-line triple-backtick fenced block at the end (``` ```[lang]\n{...}\n``` ```)
    """
    trailing_fence = _TRAILING_TRIPLE_FENCE_PATTERN.search(text)
    if trailing_fence:
        try:
            parsed = parse_verdict_line(trailing_fence.group(1))
        except VerdictParseError:
            return None
        verdict_value = parsed.get("verdict")
        if isinstance(verdict_value, str):
            return verdict_value
        return None

    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        looks_like_json = stripped.startswith("{") or stripped.startswith("`")
        if not looks_like_json:
            return None
        try:
            parsed = parse_verdict_line(stripped)
        except VerdictParseError:
            return None
        verdict_value = parsed.get("verdict")
        if isinstance(verdict_value, str):
            return verdict_value
        return None
    return None


def _extract_from_verdict_prefix(text: str) -> str | None:
    """Return the content after a `VERDICT:` prefix line (backward-compat), or None."""
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped.startswith("VERDICT:"):
            return stripped[len("VERDICT:"):].strip()
    return None


def extract_verdict_from_text(text: str) -> str:
    """Extract a verdict string from arbitrary review text.

    Tries in priority order:
    1. YAML frontmatter ``verdict:`` field
    2. JSON object (optionally fence-wrapped) as the last non-empty line
    3. ``VERDICT:`` prefix line (backward-compat with pre-W1 convention)

    Returns ``"UNKNOWN"`` when no recognizable format is present.
    """
    if not text or not text.strip():
        return "UNKNOWN"

    from_frontmatter = _extract_from_frontmatter(text)
    if from_frontmatter:
        return from_frontmatter

    from_json = _extract_from_json_last_line(text)
    if from_json:
        return from_json

    from_prefix = _extract_from_verdict_prefix(text)
    if from_prefix:
        return from_prefix

    return "UNKNOWN"
