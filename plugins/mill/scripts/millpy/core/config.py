"""
config.py — Minimal YAML parser and config resolver for millpy.

Reads _millhouse/config.yaml with no third-party dependencies. Handles the
subset of YAML used by mill: flat top-level scalars, nested mappings one level
deep, quoted and unquoted scalars, block-scalar (|) values, and comments.

This module is the canonical home for the minimal YAML parser in millpy.
tasks/status_md.py and worktree/children.py import _parse_yaml_mapping from
here — do not duplicate the parsing logic elsewhere.
"""
from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class ConfigError(ValueError):
    """Raised when _millhouse/config.yaml is malformed or a reviewer name cannot be resolved."""


# ---------------------------------------------------------------------------
# Internal YAML parsing helpers
# ---------------------------------------------------------------------------

def _coerce_scalar(raw: str) -> object:
    """Coerce an unquoted scalar string to its Python type.

    Returns bool, int, None, or str.
    """
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw in ("null", "~", ""):
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    return raw


def _strip_comment(text: str) -> str:
    """Strip an end-of-line comment from a raw value string.

    Only strips if the '#' is preceded by whitespace (to avoid stripping
    '#' embedded in unquoted strings that don't use the comment convention).
    For simplicity and correctness with the mill config format, strip any
    ' #...' suffix.
    """
    idx = text.find(" #")
    if idx != -1:
        return text[:idx].rstrip()
    return text.rstrip()


def _parse_scalar_value(raw: str) -> object:
    """Parse a raw value string (after the colon) into a Python value.

    Handles:
      - Double-quoted strings: strip quotes, return as str (no coercion)
      - Single-quoted strings: strip quotes, return as str (no coercion)
      - Unquoted scalars: coerce to bool/int/None/str
    """
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return raw[1:-1]
    if raw.startswith("'") and raw.endswith("'") and len(raw) >= 2:
        return raw[1:-1]
    return _coerce_scalar(raw)


def _parse_lines_at_indent(
    lines: list[str], start: int, parent_indent: int
) -> tuple[dict, int]:
    """Parse indented YAML mapping lines starting at `start`.

    Reads lines whose indent is strictly greater than `parent_indent`.
    Returns (parsed_dict, next_line_index).

    Supports block-scalar (|) values and recursive nested mappings (used for
    config.yaml which has two-level nesting like models.plan-review.default).
    """
    result: dict = {}
    n = len(lines)
    i = start

    while i < n:
        raw = lines[i]
        stripped = raw.strip()

        # Skip blank or comment-only lines
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        indent = len(raw) - len(raw.lstrip())

        # If we've come back to or before the parent indent, stop
        if indent <= parent_indent:
            break

        # Must have a colon to be a key-value pair
        if ":" not in stripped:
            i += 1
            continue

        colon_idx = stripped.index(":")
        key = str(stripped[:colon_idx].strip())
        rest = stripped[colon_idx + 1:]
        value_raw = rest.strip()

        # Block scalar (|)
        if value_raw == "|":
            i += 1
            block_lines = []
            common_indent: int | None = None
            while i < n:
                block_raw = lines[i]
                block_stripped = block_raw.strip()
                if block_stripped == "":
                    block_lines.append("")
                    i += 1
                    continue
                block_indent = len(block_raw) - len(block_raw.lstrip())
                if block_indent <= indent:
                    break
                if common_indent is None:
                    common_indent = block_indent
                elif block_indent < common_indent:
                    break
                block_lines.append(block_raw)
                i += 1
            if common_indent is None:
                result[key] = ""
            else:
                stripped_block = []
                for bl in block_lines:
                    if bl == "":
                        stripped_block.append("")
                    else:
                        stripped_block.append(bl[common_indent:])
                block_value = "\n".join(stripped_block)
                if not block_value.endswith("\n"):
                    block_value += "\n"
                result[key] = block_value
            continue

        # Nested mapping: value part is empty → recurse
        if value_raw == "":
            # Check if the next non-blank line has greater indent
            j = i + 1
            while j < n and (not lines[j].strip() or lines[j].strip().startswith("#")):
                j += 1
            if j < n:
                next_indent = len(lines[j]) - len(lines[j].lstrip())
                if next_indent > indent:
                    nested, i = _parse_lines_at_indent(lines, i + 1, indent)
                    result[key] = nested if nested else None
                    continue
            result[key] = None
            i += 1
            continue

        # Regular scalar value
        value_clean = _strip_comment(value_raw)
        result[key] = _parse_scalar_value(value_clean)
        i += 1

    return result, i


def _parse_yaml_mapping(text: str) -> dict:
    """Parse a minimal YAML mapping text into a Python dict.

    Supports:
    - Top-level key: value pairs (scalar values)
    - Nested mappings (recursively, multiple levels deep)
    - Integer keys normalized to strings
    - Quoted strings (no type coercion)
    - Unquoted scalars with type coercion (bool/int/null)
    - End-of-line comments stripped
    - Block-scalar (|) values: multi-line, indent stripped, joined with newline

    This is a private helper exported for use by tasks/status_md.py and
    worktree/children.py. Do not duplicate this logic in those modules.
    """
    result, _ = _parse_lines_at_indent(text.splitlines(), 0, -1)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load(path: Path) -> dict:
    """Read and parse a YAML config file.

    Parameters
    ----------
    path:
        Absolute or relative path to the YAML file.

    Returns
    -------
    dict
        Parsed configuration as a nested dict.

    Raises
    ------
    ConfigError
        If the file cannot be read or parsed.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Cannot read config file {path}: {exc}") from exc

    try:
        return _parse_yaml_mapping(text)
    except Exception as exc:
        raise ConfigError(f"Failed to parse config file {path}: {exc}") from exc


# ---------------------------------------------------------------------------
# Legacy ensemble-name aliases (pre-W1 names kept resolving to new short form
# during the migration window — see proposal 01 / Step 7).
# ---------------------------------------------------------------------------

_LEGACY_ENSEMBLE_ALIASES: dict[str, str] = {
    "ensemble-gemini3flash-x3-sonnetmax": "g3flash-x3-sonnetmax",
    "ensemble-gemini3pro-x2-opus": "g3pro-x2-opus",
    "ensemble-gemini3pro-x2-gemini3flash": "g3pro-x2-g3flash",
}


def _apply_legacy_alias(name: str) -> str:
    """Return the modern reviewer name for a legacy ensemble name."""
    return _LEGACY_ENSEMBLE_ALIASES.get(name, name)


def resolve_reviewer_name(cfg: dict, phase: str, round_number: int) -> str:
    """Resolve the reviewer name for a given phase and round.

    Canonical resolution order (first found wins):
    1. cfg["pipeline"][f"{phase}-review"][str(round_number)]
    2. cfg["pipeline"][f"{phase}-review"]["default"]

    Legacy fallback (pre-W1 schemas kept resolving during the migration
    window):
    3. cfg["review-modules"][phase][str(round_number)]
    4. cfg["review-modules"][phase]["default"]
    5. cfg["models"][f"{phase}-review"][str(round_number)]
    6. cfg["models"][f"{phase}-review"]["default"]

    Any resolved name is run through the legacy ensemble-name alias
    table before returning, so pre-rename configs that still contain
    ``ensemble-gemini3flash-x3-sonnetmax`` etc. keep working.

    Parameters
    ----------
    cfg:
        Parsed config dict from load().
    phase:
        Review phase: "discussion", "plan", or "code".
    round_number:
        1-based round index.

    Returns
    -------
    str
        The reviewer name string, with legacy aliases normalized to the
        modern short form.

    Raises
    ------
    ConfigError
        If no reviewer name can be resolved from any path.
    """
    round_str = str(round_number)
    tried: list[str] = []
    review_key = f"{phase}-review"

    pipeline = cfg.get("pipeline", {})
    if isinstance(pipeline, dict):
        pipeline_block = pipeline.get(review_key, {})
        if isinstance(pipeline_block, dict):
            if round_str in pipeline_block:
                return _apply_legacy_alias(str(pipeline_block[round_str]))
            tried.append(f"pipeline.{review_key}.{round_str}")
            if "default" in pipeline_block:
                return _apply_legacy_alias(str(pipeline_block["default"]))
            tried.append(f"pipeline.{review_key}.default")
        else:
            tried.append(f"pipeline.{review_key}.{round_str}")
            tried.append(f"pipeline.{review_key}.default")

    rm = cfg.get("review-modules", {})
    if isinstance(rm, dict):
        phase_block = rm.get(phase, {})
        if isinstance(phase_block, dict):
            if round_str in phase_block:
                return _apply_legacy_alias(str(phase_block[round_str]))
            tried.append(f"review-modules.{phase}.{round_str}")
            if "default" in phase_block:
                return _apply_legacy_alias(str(phase_block["default"]))
            tried.append(f"review-modules.{phase}.default")
        else:
            tried.append(f"review-modules.{phase}.{round_str}")
            tried.append(f"review-modules.{phase}.default")

    models = cfg.get("models", {})
    if isinstance(models, dict):
        legacy_block = models.get(review_key, {})
        if isinstance(legacy_block, dict):
            if round_str in legacy_block:
                return _apply_legacy_alias(str(legacy_block[round_str]))
            tried.append(f"models.{review_key}.{round_str}")
            if "default" in legacy_block:
                return _apply_legacy_alias(str(legacy_block["default"]))
            tried.append(f"models.{review_key}.default")
        else:
            tried.append(f"models.{review_key}.{round_str}")
            tried.append(f"models.{review_key}.default")

    raise ConfigError(
        f"Cannot resolve reviewer name for phase={phase!r} round={round_number}. "
        f"Tried: {', '.join(tried)}"
    )


def resolve_max_rounds(cfg: dict, phase: str) -> int:
    """Return the maximum review round count for a phase.

    Canonical path: cfg["pipeline"][f"{phase}-review"]["rounds"].
    Legacy fallback: cfg["reviews"][phase].
    Returns 3 if nothing is set.

    Parameters
    ----------
    cfg:
        Parsed config dict from load().
    phase:
        Review phase: "discussion", "plan", or "code".

    Returns
    -------
    int
        Maximum number of review rounds (default 3).
    """
    pipeline = cfg.get("pipeline", {})
    if isinstance(pipeline, dict):
        block = pipeline.get(f"{phase}-review", {})
        if isinstance(block, dict) and "rounds" in block:
            try:
                return int(block["rounds"])
            except (TypeError, ValueError):
                pass

    reviews = cfg.get("reviews", {})
    if isinstance(reviews, dict):
        value = reviews.get(phase)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    return 3
