"""
status_md.py — Parser and writer for _millhouse/task/status.md.

Reads the YAML code block using the shared _parse_yaml_mapping helper from
millpy.core.config. Does NOT re-implement the YAML parser. Supports nested
mappings (for forward-compat with Proposal 05's current_subprocess:) and
multi-line block-scalar values (for task_description: |).

The save() function uses a module-local YAML serializer tuned for the specific
output shape of status.md (scalar fields + one optional block scalar for
task_description).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from millpy.core.config import _parse_yaml_mapping


# ---------------------------------------------------------------------------
# YAML block extraction patterns
# ---------------------------------------------------------------------------

# Matches the ```yaml ... ``` block in status.md
_YAML_FENCE_RE = re.compile(
    r"(```yaml\n)(.*?)(```)",
    re.DOTALL,
)

# Matches the ```text ... ``` block for the Timeline section
_TIMELINE_FENCE_RE = re.compile(
    r"(```text\n)(.*?)(```)",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# YAML serializer (emit only — not a general YAML writer)
# ---------------------------------------------------------------------------

def _serialize_value(value: object) -> str:
    """Serialize a Python value to a YAML scalar string."""
    if value is None:
        return "~"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return str(value)


def _emit_yaml(data: dict) -> str:
    """Emit a YAML mapping to a string.

    Handles:
    - Scalar values (str, int, bool, None)
    - Multi-line string values emitted as block scalars (|)
    - Nested dicts emitted as indented mappings (one level deep)

    The output is suitable for re-inserting into the status.md YAML fence.
    """
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for subkey, subvalue in value.items():
                lines.append(f"  {subkey}: {_serialize_value(subvalue)}")
        elif isinstance(value, str) and "\n" in value:
            # Multi-line → block scalar
            lines.append(f"{key}: |")
            for subline in value.splitlines():
                lines.append(f"  {subline}")
        else:
            lines.append(f"{key}: {_serialize_value(value)}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load(path: Path) -> dict:
    """Parse the YAML code block from status.md into a dict.

    Parameters
    ----------
    path:
        Path to the status.md file.

    Returns
    -------
    dict
        Parsed YAML data.

    Raises
    ------
    ValueError
        If the file contains no YAML code block.
    """
    text = path.read_text(encoding="utf-8")
    m = _YAML_FENCE_RE.search(text)
    if not m:
        raise ValueError(
            f"No YAML code block found in {path}. "
            "Expected ```yaml ... ``` fences."
        )
    yaml_body = m.group(2)
    return _parse_yaml_mapping(yaml_body)


def save(path: Path, data: dict) -> None:
    """Write the data dict back into the YAML code block in status.md.

    Preserves all content outside the YAML code block (# Status heading,
    ## Timeline section, any other sections).

    Parameters
    ----------
    path:
        Path to the status.md file.
    data:
        Dict to serialize into the YAML block.
    """
    text = path.read_text(encoding="utf-8")
    yaml_content = _emit_yaml(data)
    new_block = f"```yaml\n{yaml_content}```"

    def replacer(m: re.Match) -> str:  # type: ignore[type-arg]
        return new_block

    new_text, count = _YAML_FENCE_RE.subn(replacer, text, count=1)
    if count == 0:
        raise ValueError(f"No YAML code block found in {path} to replace.")
    path.write_text(new_text, encoding="utf-8")


def update_phase(path: Path, phase: str) -> None:
    """Set the phase field in status.md.

    Convenience wrapper: load → set phase → save.

    Parameters
    ----------
    path:
        Path to the status.md file.
    phase:
        New phase string (e.g. "implementing", "testing").
    """
    data = load(path)
    data["phase"] = phase
    save(path, data)


def append_timeline(path: Path, entry: str) -> None:
    """Append an entry to the ## Timeline text block.

    Inserts `<entry>  <UTC-timestamp>` on a new line immediately before the
    closing ``` of the ## Timeline code block.

    Parameters
    ----------
    path:
        Path to the status.md file.
    entry:
        The timeline entry string (e.g. "implementing", "plan-review-r1").
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new_line = f"{entry}              {timestamp}"

    text = path.read_text(encoding="utf-8")

    # Find the Timeline section's text fence
    # Strategy: split on the second ``` that follows ## Timeline
    timeline_section_re = re.compile(
        r"(## Timeline\s*\n\s*```text\n)(.*?)(```)",
        re.DOTALL,
    )
    m = timeline_section_re.search(text)
    if not m:
        # Fallback: append to the last ```text block
        m2 = _TIMELINE_FENCE_RE.search(text)
        if not m2:
            raise ValueError(f"No Timeline text block found in {path}.")
        fence_open = m2.group(1)
        fence_body = m2.group(2)
        fence_close = m2.group(3)
        if not fence_body.endswith("\n"):
            fence_body += "\n"
        new_body = fence_open + fence_body + new_line + "\n" + fence_close
        new_text = text[:m2.start()] + new_body + text[m2.end():]
    else:
        fence_open = m.group(1)
        fence_body = m.group(2)
        fence_close = m.group(3)
        if not fence_body.endswith("\n"):
            fence_body += "\n"
        new_body = fence_open + fence_body + new_line + "\n" + fence_close
        new_text = text[:m.start()] + new_body + text[m.end():]

    path.write_text(new_text, encoding="utf-8")
