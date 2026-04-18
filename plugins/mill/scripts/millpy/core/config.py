"""
config.py — Minimal YAML parser and config resolver for millpy.

Reads _millhouse/config.yaml with no third-party dependencies. Handles the
subset of YAML used by mill: flat top-level scalars, nested mappings one level
deep, quoted and unquoted scalars, block-scalar (|) values, and comments.

This module is the canonical home for the minimal YAML parser in millpy.
tasks/status_md.py and worktree/children.py import _parse_yaml_mapping from
here — do not duplicate the parsing logic elsewhere.

Config schema (new wiki-based system)
--------------------------------------
Two sources are merged by ``load_merged()``:

Shared config (``.mill/config.yaml``, tracked in wiki):
  git:          git workflow settings (auto-merge, branch-prefix, …)
  repo:         repo metadata (short-name, branch-prefix)
  pipeline:     review pipeline configuration (reviewer names, rounds)
  runtime:      runtime settings (implementer model, …)
  revise:       revise-tasks settings

Local config (``_millhouse/config.local.yaml``, gitignored):
  notifications:  platform notification settings (slack, desktop)
  wiki:           wiki override settings
    clone-path:   (str, optional) absolute path to local wiki clone

Merge rule: deep-merge per top-level key. Local values override shared values
at any nested depth. Lists are replaced (not concatenated). A missing file is
treated as empty.
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


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge ``override`` into ``base`` and return a new dict.

    Rules:
    - If both values for a key are dicts, recurse.
    - Otherwise, override value wins (lists are replaced, not concatenated).
    - Keys present only in ``base`` are kept.
    - Keys present only in ``override`` are added.

    Parameters
    ----------
    base:
        The base dict (e.g. shared config).
    override:
        The override dict (e.g. local config).

    Returns
    -------
    dict
        Merged dict. Neither input is mutated.
    """
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_merged(
    shared_path: Path,
    local_path: Path,
    legacy_path: Path | None = None,
) -> dict:
    """Load and merge shared + local config files.

    Resolution order:
    1. **Shared config:** ``shared_path`` (``.mill/config.yaml``).
       If missing, falls back to ``legacy_path`` (``_millhouse/config.yaml``)
       when provided — temporary bootstrap until ``mill-setup`` splits the
       config. Logs a DEBUG message on the legacy path.
    2. **Local config:** ``local_path`` (``_millhouse/config.local.yaml``).
       Missing → treated as empty.

    Merge rule: deep-merge per top-level key. Local values override shared
    values at any nested depth. Lists are replaced (not concatenated).

    Parameters
    ----------
    shared_path:
        Path to the shared config (``.mill/config.yaml``).
    local_path:
        Path to the local config (``_millhouse/config.local.yaml``).
    legacy_path:
        Optional fallback for the shared config when ``shared_path`` is absent.

    Returns
    -------
    dict
        Merged configuration dict. Empty dict when all sources are absent.
    """
    import sys  # local import — log to stderr, no log_util dependency at module level

    # Load shared config (with legacy fallback).
    shared: dict = {}
    if shared_path.exists():
        shared = load(shared_path)
    elif legacy_path is not None and legacy_path.exists():
        sys.stderr.write(
            f"[config] DEBUG: .mill/config.yaml not found; "
            f"falling back to legacy {legacy_path} (run mill-setup to migrate)\n"
        )
        sys.stderr.flush()
        shared = load(legacy_path)

    # Load local overrides.
    local: dict = {}
    if local_path.exists():
        local = load(local_path)

    if not local:
        return shared

    return _deep_merge(shared, local)


def resolve_reviewer_name(
    cfg: dict,
    phase: str,
    round_number: int,
) -> str:
    """Resolve the reviewer name for a given phase and round.

    Resolution order (first found wins):
    1. cfg["pipeline"][f"{phase}-review"][str(round_number)]
    2. cfg["pipeline"][f"{phase}-review"]["default"]

    Per-card/holistic slice_type branching has been removed (Card 5). The
    resolver is now slice-type-agnostic: every review phase uses a single
    holistic reviewer per round, with optional per-round integer key overrides.

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
        The reviewer name string.

    Raises
    ------
    ConfigError
        If no reviewer name can be resolved.
    """
    tried: list[str] = []
    review_key = f"{phase}-review"

    pipeline = cfg.get("pipeline", {})
    if isinstance(pipeline, dict):
        pipeline_block = pipeline.get(review_key, {})
        if isinstance(pipeline_block, dict):
            # round-based resolution: look up round number, fall back to default
            round_str = str(round_number)
            if round_str in pipeline_block:
                return str(pipeline_block[round_str])
            tried.append(f"pipeline.{review_key}.{round_str}")

            if "default" in pipeline_block:
                return str(pipeline_block["default"])
            tried.append(f"pipeline.{review_key}.default")
        else:
            tried.append(f"pipeline.{review_key}.{round_number}")
            tried.append(f"pipeline.{review_key}.default")

    raise ConfigError(
        f"Cannot resolve reviewer name for phase={phase!r} round={round_number}"
        f". Tried: {', '.join(tried)}"
    )


def resolve_max_rounds(cfg: dict, phase: str) -> int:
    """Return the maximum review round count for a phase.

    Path: cfg["pipeline"][f"{phase}-review"]["rounds"].
    Returns 3 if not set.

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
    return 3
