"""
plan_validator.py — Structural validation for v1 and v2 plan files.

The authoritative check list for this module is documented in
plugins/mill/doc/formats/validation.md. This is the Python implementation
that mill-go Phase: Plan and spawn_reviewer.py call to validate plan structure
before proceeding.

Never raises on validation failures — returns a list of ValidationError
objects. Only raises on structural corruption that prevents any parsing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from millpy.core.plan_io import PlanLocation, parse_frontmatter


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------

@dataclass
class ValidationError:
    """A single structural validation finding.

    Fields
    ------
    severity:
        Always "BLOCKING" for checks in this module. "WARNING" reserved for
        future non-blocking checks.
    location:
        Repo-relative file path, optionally with `:<line>` suffix.
    message:
        Human-readable description of the violation.
    """
    severity: Literal["BLOCKING", "WARNING"]
    location: str
    message: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate(loc: PlanLocation) -> list[ValidationError]:
    """Validate the structural integrity of a plan.

    Parameters
    ----------
    loc:
        Resolved plan location from `plan_io.resolve_plan_path`.

    Returns
    -------
    list[ValidationError]
        Empty list for valid plans, populated list for invalid plans.
        Never raises on validation failures.

    Raises
    ------
    OSError
        If a required file cannot be read (structural corruption).
    """
    if loc.kind == "v1":
        return _validate_v1(loc)
    else:
        return _validate_v2(loc)


# ---------------------------------------------------------------------------
# v1 validation
# ---------------------------------------------------------------------------

_V1_REQUIRED_FM_KEYS = ["verify", "dev-server", "approved", "started"]
_V1_REQUIRED_SECTIONS = ["## Context", "## Files", "## Steps"]


def _validate_v1(loc: PlanLocation) -> list[ValidationError]:
    errors: list[ValidationError] = []
    text = loc.path.read_text(encoding="utf-8")
    rel = _to_repo_rel(loc.path)

    # Frontmatter
    fm = parse_frontmatter(text)
    for key in _V1_REQUIRED_FM_KEYS:
        if key not in fm or fm[key] is None:
            errors.append(ValidationError(
                severity="BLOCKING",
                location=rel,
                message=f"Frontmatter missing required key: '{key}'",
            ))

    # Required sections
    for section in _V1_REQUIRED_SECTIONS:
        if not _has_section(text, section):
            errors.append(ValidationError(
                severity="BLOCKING",
                location=rel,
                message=f"Required section missing: {section}",
            ))

    # Step cards
    cards = _parse_step_cards(text)
    seen_step_nums: list[int] = []
    for step_num, card_text in cards:
        errors.extend(_validate_card_common(card_text, step_num, rel, seen_step_nums, v2=False))
        seen_step_nums.append(step_num)

    return errors


# ---------------------------------------------------------------------------
# v2 validation
# ---------------------------------------------------------------------------

_V2_OVERVIEW_REQUIRED_FM_KEYS = ["kind", "task", "verify", "dev-server", "approved", "started", "batches"]
_V2_BATCH_REQUIRED_FM_KEYS = ["kind", "batch-name", "batch-depends", "approved"]
_V2_OVERVIEW_REQUIRED_SECTIONS = [
    "## Context",
    "## Shared Constraints",
    "## Shared Decisions",
    "## Batch Graph",
    "## All Files Touched",
]
_V2_BATCH_REQUIRED_SECTIONS = ["## Batch-Specific Context", "## Batch Files", "## Steps"]


def _validate_v2(loc: PlanLocation) -> list[ValidationError]:
    errors: list[ValidationError] = []

    # Validate overview
    overview_text = loc.overview.read_text(encoding="utf-8")  # type: ignore[union-attr]
    overview_rel = _to_repo_rel(loc.overview)  # type: ignore[arg-type]
    overview_fm = parse_frontmatter(overview_text)

    # Overview frontmatter keys
    for key in _V2_OVERVIEW_REQUIRED_FM_KEYS:
        if key not in overview_fm or overview_fm[key] is None:
            errors.append(ValidationError(
                severity="BLOCKING",
                location=overview_rel,
                message=f"Frontmatter missing required key: '{key}'",
            ))

    # Overview sections
    for section in _V2_OVERVIEW_REQUIRED_SECTIONS:
        if not _has_section(overview_text, section):
            errors.append(ValidationError(
                severity="BLOCKING",
                location=overview_rel,
                message=f"Required section missing: {section}",
            ))

    # Collect known batch slugs from overview
    batches_list = overview_fm.get("batches", [])
    if isinstance(batches_list, list):
        known_batch_slugs = set(batches_list)
    else:
        known_batch_slugs = set()

    # Collect all step numbers across batches for uniqueness check
    all_step_nums_global: list[int] = []
    step_num_to_batch: dict[int, str] = {}

    # Validate each batch file
    for batch_path in loc.batches:
        batch_text = batch_path.read_text(encoding="utf-8")
        batch_rel = _to_repo_rel(batch_path)
        batch_fm = parse_frontmatter(batch_text)

        # Batch frontmatter keys
        for key in _V2_BATCH_REQUIRED_FM_KEYS:
            if key not in batch_fm or batch_fm[key] is None:
                errors.append(ValidationError(
                    severity="BLOCKING",
                    location=batch_rel,
                    message=f"Frontmatter missing required key: '{key}'",
                ))

        # batch-depends references must resolve
        batch_deps = batch_fm.get("batch-depends", [])
        if isinstance(batch_deps, list):
            for dep_slug in batch_deps:
                if dep_slug and dep_slug not in known_batch_slugs:
                    errors.append(ValidationError(
                        severity="BLOCKING",
                        location=batch_rel,
                        message=f"batch-depends references unknown batch: '{dep_slug}'",
                    ))
        valid_dep_slugs = set(batch_deps) if isinstance(batch_deps, list) else set()

        # Batch sections
        for section in _V2_BATCH_REQUIRED_SECTIONS:
            if not _has_section(batch_text, section):
                errors.append(ValidationError(
                    severity="BLOCKING",
                    location=batch_rel,
                    message=f"Required section missing: {section}",
                ))

        # Step cards in this batch
        cards = _parse_step_cards(batch_text)
        batch_step_nums = [n for n, _ in cards]

        # Global uniqueness check
        for step_num in batch_step_nums:
            if step_num in step_num_to_batch:
                errors.append(ValidationError(
                    severity="BLOCKING",
                    location=batch_rel,
                    message=(
                        f"Card numbering collision: step {step_num} appears in both "
                        f"'{step_num_to_batch[step_num]}' and '{batch_rel}'"
                    ),
                ))
            else:
                step_num_to_batch[step_num] = batch_rel

        all_step_nums_global.extend(batch_step_nums)

        # Validate individual cards (v2-aware)
        # For depends-on resolution, a card may reference steps in earlier
        # batches (via batch-depends) or within this batch. We pass the
        # global list accumulated so far (steps from earlier batches + this
        # batch's earlier cards).
        for step_num, card_text in cards:
            earlier_in_batch = [n for n in batch_step_nums if n < step_num]
            steps_from_prior_batches = [
                n for n in step_num_to_batch if n not in batch_step_nums
            ]
            valid_step_nums = earlier_in_batch + steps_from_prior_batches
            errors.extend(_validate_card_common(
                card_text, step_num, batch_rel, valid_step_nums, v2=True,
            ))

    return errors


# ---------------------------------------------------------------------------
# Per-card validation
# ---------------------------------------------------------------------------

def _validate_card_common(
    card_text: str,
    step_num: int,
    location: str,
    valid_dep_step_nums: list[int],
    *,
    v2: bool,
) -> list[ValidationError]:
    """Validate a single step card, returning any errors."""
    errors: list[ValidationError] = []

    creates_val = _extract_field(card_text, "Creates")
    modifies_val = _extract_field(card_text, "Modifies")

    # Both Creates and Modifies none → structural violation
    creates_empty = creates_val is None or creates_val.strip().lower() == "none"
    modifies_empty = modifies_val is None or modifies_val.strip().lower() == "none"
    if creates_empty and modifies_empty:
        errors.append(ValidationError(
            severity="BLOCKING",
            location=location,
            message=f"Step {step_num}: both Creates and Modifies are 'none' — card does nothing",
        ))

    # depends-on validation
    depends_on_raw = _extract_field(card_text, "depends-on")
    if depends_on_raw is not None:
        dep_nums = _parse_int_list(depends_on_raw)
        for dep in dep_nums:
            if dep not in valid_dep_step_nums:
                errors.append(ValidationError(
                    severity="BLOCKING",
                    location=location,
                    message=f"Step {step_num}: depends-on references non-existent step {dep}",
                ))

    # v2-only checks
    if v2:
        reads_val = _extract_field(card_text, "Reads")
        reads_empty = reads_val is None or reads_val.strip().lower() == "none" or not reads_val.strip()
        if reads_empty:
            errors.append(ValidationError(
                severity="BLOCKING",
                location=location,
                message=f"Step {step_num}: Reads field is empty or missing (required in v2)",
            ))
        else:
            # Extract individual paths from Reads
            reads_paths = _extract_bullet_paths(reads_val)
            explore_val = _extract_field(card_text, "Explore")
            if explore_val:
                explore_paths = _extract_bullet_paths(explore_val)
                for ep in explore_paths:
                    if ep not in reads_paths:
                        errors.append(ValidationError(
                            severity="BLOCKING",
                            location=location,
                            message=(
                                f"Step {step_num}: Explore path '{ep}' is not in Reads "
                                f"(Explore ⊆ Reads required in v2)"
                            ),
                        ))

    return errors


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _has_section(text: str, heading: str) -> bool:
    """Return True if the exact heading appears on its own line."""
    return any(line.strip() == heading for line in text.splitlines())


def _parse_step_cards(text: str) -> list[tuple[int, str]]:
    """Return list of (step_number, card_text) tuples from a plan/batch body."""
    lines = text.splitlines(keepends=True)
    cards: list[tuple[int, str]] = []
    current_num: int | None = None
    current_lines: list[str] = []

    step_re = re.compile(r"^###\s+Step\s+(\d+)\s*:", re.IGNORECASE)

    for line in lines:
        m = step_re.match(line)
        if m:
            if current_num is not None:
                cards.append((current_num, "".join(current_lines)))
            current_num = int(m.group(1))
            current_lines = [line]
        elif current_num is not None:
            # Stop at a higher-level heading
            if line.startswith("##") and not line.startswith("###"):
                cards.append((current_num, "".join(current_lines)))
                current_num = None
                current_lines = []
            else:
                current_lines.append(line)

    if current_num is not None:
        cards.append((current_num, "".join(current_lines)))

    return cards


def _extract_field(card_text: str, field_name: str) -> str | None:
    """Extract the value of a **FieldName:** bullet in a card.

    Returns the content starting from the field line through the end of the
    field's value (which may span multiple indented sub-lines). Stops when
    another top-level `- **...**:` field is encountered.

    Returns None if the field is absent.
    """
    field_re = re.compile(
        rf"^\s*-\s+\*\*{re.escape(field_name)}:\*\*\s*(.*)",
        re.IGNORECASE,
    )
    # Any line that starts a new bolded field
    other_field_re = re.compile(r"^\s*-\s+\*\*\w[^*]*:\*\*")

    lines = card_text.splitlines()
    found = False
    collected: list[str] = []

    for line in lines:
        if not found:
            m = field_re.match(line)
            if m:
                found = True
                collected.append(m.group(1))
        else:
            # Stop at the next top-level field
            if other_field_re.match(line):
                break
            collected.append(line)

    if not found:
        return None
    return "\n".join(collected)


def _extract_bullet_paths(field_value: str) -> set[str]:
    """Extract backtick-wrapped path tokens from a bullet-list field value.

    Handles values like:
      `plugins/mill/foo.py`, `plugins/mill/bar.py`
    or multi-line:
      - `plugins/mill/foo.py` — description
    """
    paths: list[str] = []
    # Find all backtick-wrapped tokens
    for match in re.finditer(r"`([^`]+)`", field_value):
        token = match.group(1).strip()
        if token:
            paths.append(token)
    return set(paths)


def _parse_int_list(raw: str) -> list[int]:
    """Parse a depends-on value like '[1, 3]' or '[]' into a list of ints."""
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        result = []
        for item in inner.split(","):
            item = item.strip()
            if item.isdigit():
                result.append(int(item))
        return result
    # Also handle space-separated or bare integers
    result = []
    for token in re.split(r"[\s,]+", raw):
        token = token.strip("[]")
        if token.isdigit():
            result.append(int(token))
    return result


def _to_repo_rel(path: Path) -> str:
    """Convert an absolute path to a repo-relative string with forward slashes.

    Falls back to the absolute path string if the repo root cannot be
    determined.
    """
    try:
        from millpy.core.paths import repo_root
        root = repo_root()
        return path.relative_to(root).as_posix()
    except Exception:
        return path.as_posix()
