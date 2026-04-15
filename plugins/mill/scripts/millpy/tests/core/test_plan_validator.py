"""
test_plan_validator.py — Tests for millpy.core.plan_validator (TDD: RED → GREEN → REFACTOR).
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from millpy.core.plan_io import resolve_plan_path
from millpy.core.plan_validator import ValidationError, validate


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def write_v1_plan(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "plan.md"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def write_v2_overview(tmp_path: Path, content: str) -> Path:
    d = tmp_path / "plan"
    d.mkdir(exist_ok=True)
    p = d / "00-overview.md"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def write_v2_batch(tmp_path: Path, filename: str, content: str) -> Path:
    d = tmp_path / "plan"
    d.mkdir(exist_ok=True)
    p = d / filename
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


VALID_V1 = """\
    ---
    verify: python -m pytest tests
    dev-server: N/A
    approved: false
    started: 20260415-120000
    ---

    # Test Task

    ## Context

    A simple task.

    ### Decision: Use foo
    **Why:** Because foo is better.
    **Alternatives rejected:** bar.

    ## Files

    - plugins/mill/foo.py

    ## Steps

    ### Step 1: Create foo.py

    - **Creates:** plugins/mill/foo.py
    - **Modifies:** none
    - **Requirements:**
      - Requirement 1.
    - **Explore:**
      - `plugins/mill/bar.py` — the pattern to follow.
    - **Test approach:** unit
    - **Key test scenarios:**
      - Happy: foo creates the file.
      - Error: file already exists.
    - **Commit:** `feat: add foo`
"""

VALID_V2_OVERVIEW = """\
    ---
    kind: plan-overview
    task: Test Task
    verify: python -m pytest tests
    dev-server: N/A
    approved: false
    started: 20260415-120000
    batches: [core, tasks]
    ---

    # Test Task

    ## Context

    A simple task.

    ## Shared Constraints

    - Use log_util.

    ## Shared Decisions

    ### Decision: Use foo
    **Why:** Because foo is better.
    **Alternatives rejected:** bar.

    ## Batch Graph

    ```yaml
    batches:
      core:
        depends-on: []
        summary: "Core."
      tasks:
        depends-on: [core]
        summary: "Tasks."
    ```

    ## All Files Touched

    - plugins/mill/foo.py
    - plugins/mill/bar.py
"""

VALID_V2_BATCH_CORE = """\
    ---
    kind: plan-batch
    batch-name: core
    batch-depends: []
    approved: false
    ---

    # Batch 01: core

    ## Batch-Specific Context

    (None.)

    ## Batch Files

    - plugins/mill/foo.py

    ## Steps

    ### Step 1: Create foo.py

    - **Creates:** plugins/mill/foo.py
    - **Modifies:** none
    - **Reads:** `plugins/mill/bar.py`
    - **Requirements:**
      - Requirement 1.
    - **Explore:**
      - `plugins/mill/bar.py` — the pattern.
    - **depends-on:** []
    - **Test approach:** unit
    - **Key test scenarios:**
      - Happy: creates the file.
      - Error: already exists.
    - **Commit:** `feat: add foo`
"""

VALID_V2_BATCH_TASKS = """\
    ---
    kind: plan-batch
    batch-name: tasks
    batch-depends: [core]
    approved: false
    ---

    # Batch 02: tasks

    ## Batch-Specific Context

    (None.)

    ## Batch Files

    - plugins/mill/bar.py

    ## Steps

    ### Step 2: Create bar.py

    - **Creates:** plugins/mill/bar.py
    - **Modifies:** none
    - **Reads:** `plugins/mill/foo.py`
    - **Requirements:**
      - Requirement 1.
    - **Explore:**
      - `plugins/mill/foo.py` — the dependency.
    - **depends-on:** [1]
    - **Test approach:** unit
    - **Key test scenarios:**
      - Happy: creates the file.
      - Error: already exists.
    - **Commit:** `feat: add bar`
"""


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_v1_valid_returns_empty_list(self, tmp_path):
        write_v1_plan(tmp_path, VALID_V1)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert errors == []

    def test_v2_valid_returns_empty_list(self, tmp_path):
        write_v2_overview(tmp_path, VALID_V2_OVERVIEW)
        write_v2_batch(tmp_path, "01-core.md", VALID_V2_BATCH_CORE)
        write_v2_batch(tmp_path, "02-tasks.md", VALID_V2_BATCH_TASKS)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert errors == []

    def test_v1_explore_does_not_trigger_v2_only_reads_check(self, tmp_path):
        """v1 cards have Explore: entries but no Reads: field — v2-only check must skip v1."""
        write_v1_plan(tmp_path, VALID_V1)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        # Must be empty — the Explore: ⊆ Reads: check does NOT fire on v1
        reads_errors = [e for e in errors if "Reads" in e.message]
        assert reads_errors == []


# ---------------------------------------------------------------------------
# v1 frontmatter errors
# ---------------------------------------------------------------------------

class TestV1FrontmatterErrors:
    def test_missing_verify(self, tmp_path):
        write_v1_plan(tmp_path, """\
            ---
            dev-server: N/A
            approved: false
            started: 20260415-120000
            ---
            ## Files
            - foo.py
            ## Steps
        """)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("verify" in e.message for e in errors)
        assert all(e.severity == "BLOCKING" for e in errors)

    def test_missing_started(self, tmp_path):
        write_v1_plan(tmp_path, """\
            ---
            verify: noop
            dev-server: N/A
            approved: false
            ---
            ## Files
            - foo.py
            ## Steps
        """)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("started" in e.message for e in errors)


# ---------------------------------------------------------------------------
# v1 section errors
# ---------------------------------------------------------------------------

class TestV1SectionErrors:
    def test_missing_files_section(self, tmp_path):
        write_v1_plan(tmp_path, """\
            ---
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260101-000000
            ---
            # Title
            ## Context
            text
            ## Steps
        """)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("## Files" in e.message for e in errors)

    def test_missing_steps_section(self, tmp_path):
        write_v1_plan(tmp_path, """\
            ---
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260101-000000
            ---
            # Title
            ## Context
            text
            ## Files
            - foo.py
        """)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("## Steps" in e.message for e in errors)

    def test_missing_context_section(self, tmp_path):
        write_v1_plan(tmp_path, """\
            ---
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260101-000000
            ---
            # Title
            ## Files
            - foo.py
            ## Steps
        """)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("## Context" in e.message for e in errors)


# ---------------------------------------------------------------------------
# Step card errors (both v1 and v2)
# ---------------------------------------------------------------------------

class TestStepCardErrors:
    def test_creates_and_modifies_both_none(self, tmp_path):
        write_v1_plan(tmp_path, """\
            ---
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260101-000000
            ---
            # Title
            ## Context
            text
            ## Files
            - foo.py
            ## Steps
            ### Step 1: Do nothing
            - **Creates:** none
            - **Modifies:** none
            - **Commit:** `feat: nothing`
        """)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("both Creates and Modifies are 'none' — card does nothing" in e.message for e in errors)

    def test_depends_on_invalid_reference(self, tmp_path):
        write_v1_plan(tmp_path, """\
            ---
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260101-000000
            ---
            # Title
            ## Context
            text
            ## Files
            - foo.py
            ## Steps
            ### Step 1: Do something
            - **Creates:** foo.py
            - **Modifies:** none
            - **depends-on:** [99]
            - **Commit:** `feat: foo`
        """)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("99" in e.message or "depends-on" in e.message.lower() for e in errors)

    def test_v1_forward_reference_rejected(self, tmp_path):
        """v1 depends-on must not allow forward references (step 1 referencing step 3)."""
        write_v1_plan(tmp_path, """\
            ---
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260101-000000
            ---
            # Title
            ## Context
            text
            ## Files
            - foo.py
            - bar.py
            - baz.py
            ## Steps
            ### Step 1: Create foo.py
            - **Creates:** foo.py
            - **Modifies:** none
            - **depends-on:** [3]
            - **Commit:** `feat: foo`
            ### Step 2: Create bar.py
            - **Creates:** bar.py
            - **Modifies:** none
            - **Commit:** `feat: bar`
            ### Step 3: Create baz.py
            - **Creates:** baz.py
            - **Modifies:** none
            - **Commit:** `feat: baz`
        """)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("depends-on" in e.message.lower() or "3" in e.message for e in errors), (
            "Expected a validation error for forward reference depends-on: [3] in step 1"
        )


# ---------------------------------------------------------------------------
# v2-only errors
# ---------------------------------------------------------------------------

class TestV2OnlyErrors:
    def test_reads_empty_triggers_error(self, tmp_path):
        write_v2_overview(tmp_path, VALID_V2_OVERVIEW)
        write_v2_batch(tmp_path, "01-core.md", """\
            ---
            kind: plan-batch
            batch-name: core
            batch-depends: []
            approved: false
            ---
            # Batch 01: core
            ## Batch-Specific Context
            (None.)
            ## Batch Files
            - foo.py
            ## Steps
            ### Step 1: Create foo.py
            - **Creates:** foo.py
            - **Modifies:** none
            - **Reads:** none
            - **Requirements:**
              - Req 1.
            - **Explore:**
              - `bar.py` — pattern.
            - **depends-on:** []
            - **Commit:** `feat: foo`
        """)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("Reads" in e.message for e in errors)

    def test_explore_not_subset_of_reads(self, tmp_path):
        write_v2_overview(tmp_path, VALID_V2_OVERVIEW)
        write_v2_batch(tmp_path, "01-core.md", """\
            ---
            kind: plan-batch
            batch-name: core
            batch-depends: []
            approved: false
            ---
            # Batch 01: core
            ## Batch-Specific Context
            (None.)
            ## Batch Files
            - foo.py
            ## Steps
            ### Step 1: Create foo.py
            - **Creates:** foo.py
            - **Modifies:** none
            - **Reads:** `foo.py`
            - **Requirements:**
              - Req 1.
            - **Explore:**
              - `bar.py` — pattern that is NOT in Reads.
            - **depends-on:** []
            - **Commit:** `feat: foo`
        """)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("bar.py" in e.message or "Explore" in e.message for e in errors)

    def test_duplicate_card_numbers(self, tmp_path):
        write_v2_overview(tmp_path, VALID_V2_OVERVIEW)
        write_v2_batch(tmp_path, "01-core.md", """\
            ---
            kind: plan-batch
            batch-name: core
            batch-depends: []
            approved: false
            ---
            # Batch 01: core
            ## Batch-Specific Context
            (None.)
            ## Batch Files
            - foo.py
            ## Steps
            ### Step 1: First
            - **Creates:** foo.py
            - **Modifies:** none
            - **Reads:** `bar.py`
            - **Explore:**
              - `bar.py` — pattern.
            - **depends-on:** []
            - **Commit:** `feat: first`
        """)
        write_v2_batch(tmp_path, "02-tasks.md", """\
            ---
            kind: plan-batch
            batch-name: tasks
            batch-depends: [core]
            approved: false
            ---
            # Batch 02: tasks
            ## Batch-Specific Context
            (None.)
            ## Batch Files
            - bar.py
            ## Steps
            ### Step 1: Duplicate
            - **Creates:** bar.py
            - **Modifies:** none
            - **Reads:** `foo.py`
            - **Explore:**
              - `foo.py` — dep.
            - **depends-on:** []
            - **Commit:** `feat: dup`
        """)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("1" in e.message and ("collision" in e.message.lower() or "duplicate" in e.message.lower() or "unique" in e.message.lower()) for e in errors)

    def test_batch_depends_invalid_reference(self, tmp_path):
        write_v2_overview(tmp_path, VALID_V2_OVERVIEW)
        write_v2_batch(tmp_path, "01-core.md", """\
            ---
            kind: plan-batch
            batch-name: core
            batch-depends: [nonexistent-batch]
            approved: false
            ---
            # Batch 01: core
            ## Batch-Specific Context
            (None.)
            ## Batch Files
            - foo.py
            ## Steps
            ### Step 1: First
            - **Creates:** foo.py
            - **Modifies:** none
            - **Reads:** `bar.py`
            - **Explore:**
              - `bar.py` — pattern.
            - **depends-on:** []
            - **Commit:** `feat: first`
        """)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("nonexistent-batch" in e.message or "batch-depends" in e.message.lower() for e in errors)

    def test_v2_overview_missing_required_sections(self, tmp_path):
        write_v2_overview(tmp_path, """\
            ---
            kind: plan-overview
            task: Test
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260101-000000
            batches: []
            ---
            # Test
            ## Context
            text
        """)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        # Should flag missing sections
        missing_sections = {e.message for e in errors}
        # At least one of the required v2 sections should be flagged
        assert any("Shared Constraints" in m or "Shared Decisions" in m or "Batch Graph" in m or "All Files Touched" in m for m in missing_sections)
