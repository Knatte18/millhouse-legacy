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


def write_v3_overview(tmp_path: Path, content: str) -> Path:
    d = tmp_path / "plan"
    d.mkdir(exist_ok=True)
    p = d / "00-overview.md"
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def write_v3_card(tmp_path: Path, filename: str, content: str) -> Path:
    d = tmp_path / "plan"
    d.mkdir(exist_ok=True)
    p = d / filename
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


VALID_V3_OVERVIEW = """\
    ---
    kind: plan-overview
    task: Test Task v3
    verify: python -m pytest tests
    dev-server: N/A
    approved: false
    started: 20260415-120000
    root: plugins/mill
    ---

    # Test Task v3

    ## Card Index

    ```yaml
    1:
      slug: add-foo
      creates: [core/foo.py]
      modifies: []
      reads: [core/bar.py]
      depends-on: []
    2:
      slug: update-bar
      creates: []
      modifies: [core/bar.py]
      reads: [core/foo.py]
      depends-on: [1]
    ```

    ## All Files Touched

    - core/foo.py
    - core/bar.py
"""

VALID_V3_CARD_1 = """\
    ---
    kind: plan-card
    card-number: 1
    card-slug: add-foo
    ---

    ### Step 1: Add foo.py

    - **Creates:** `core/foo.py`
    - **Modifies:** none
    - **Reads:** `core/bar.py`
    - **Requirements:**
      - Requirement 1.
    - **Explore:**
      - `core/bar.py` — pattern to follow.
    - **depends-on:** []
    - **Commit:** `feat: add foo`
"""

VALID_V3_CARD_2 = """\
    ---
    kind: plan-card
    card-number: 2
    card-slug: update-bar
    ---

    ### Step 2: Update bar.py

    - **Creates:** none
    - **Modifies:** `core/bar.py`
    - **Reads:** `core/foo.py`
    - **Requirements:**
      - Requirement 1.
    - **Explore:**
      - `core/foo.py` — existing pattern.
    - **depends-on:** [1]
    - **Commit:** `feat: update bar`
"""


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_v3_valid_returns_empty_list(self, tmp_path):
        write_v3_overview(tmp_path, VALID_V3_OVERVIEW)
        write_v3_card(tmp_path, "card-01-add-foo.md", VALID_V3_CARD_1)
        write_v3_card(tmp_path, "card-02-update-bar.md", VALID_V3_CARD_2)
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert errors == []

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


# ---------------------------------------------------------------------------
# v3-only errors
# ---------------------------------------------------------------------------

class TestV3OnlyErrors:
    def test_v3_card_file_missing_for_index_entry(self, tmp_path):
        """Card Index references card 2 but no card-02-*.md file exists."""
        write_v3_overview(tmp_path, VALID_V3_OVERVIEW)
        write_v3_card(tmp_path, "card-01-add-foo.md", VALID_V3_CARD_1)
        # card-02-update-bar.md intentionally absent
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("2" in e.message and ("missing" in e.message.lower() or "no matching" in e.message.lower()) for e in errors)
        assert all(e.severity == "BLOCKING" for e in errors)

    def test_v3_card_number_gap(self, tmp_path):
        """Card numbers 1, 2, 4 — gap at 3 should be a BLOCKING error."""
        overview = textwrap.dedent("""\
            ---
            kind: plan-overview
            task: Gapped
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260415-120000
            root: ""
            ---
            ## Card Index
            ```yaml
            1:
              slug: a
              creates: [a.py]
              modifies: []
              reads: []
              depends-on: []
            2:
              slug: b
              creates: [b.py]
              modifies: []
              reads: []
              depends-on: [1]
            4:
              slug: d
              creates: [d.py]
              modifies: []
              reads: []
              depends-on: [2]
            ```
            ## All Files Touched
            - a.py
        """)
        write_v3_overview(tmp_path, overview)
        write_v3_card(tmp_path, "card-01-a.md", textwrap.dedent("""\
            ---
            kind: plan-card
            card-number: 1
            card-slug: a
            ---
            ### Step 1: A
            - **Creates:** `a.py`
            - **Modifies:** none
            - **Reads:** none
            - **depends-on:** []
            - **Commit:** `feat: a`
        """))
        write_v3_card(tmp_path, "card-02-b.md", textwrap.dedent("""\
            ---
            kind: plan-card
            card-number: 2
            card-slug: b
            ---
            ### Step 2: B
            - **Creates:** `b.py`
            - **Modifies:** none
            - **Reads:** none
            - **depends-on:** [1]
            - **Commit:** `feat: b`
        """))
        write_v3_card(tmp_path, "card-04-d.md", textwrap.dedent("""\
            ---
            kind: plan-card
            card-number: 4
            card-slug: d
            ---
            ### Step 4: D
            - **Creates:** `d.py`
            - **Modifies:** none
            - **Reads:** none
            - **depends-on:** [2]
            - **Commit:** `feat: d`
        """))
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("sequential" in e.message.lower() or "gap" in e.message.lower() for e in errors)

    def test_v3_depends_on_nonexistent_card(self, tmp_path):
        """depends-on references card 99 which doesn't exist."""
        write_v3_overview(tmp_path, textwrap.dedent("""\
            ---
            kind: plan-overview
            task: Bad Dep
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260415-120000
            root: ""
            ---
            ## Card Index
            ```yaml
            1:
              slug: bad-dep
              creates: [foo.py]
              modifies: []
              reads: []
              depends-on: [99]
            ```
            ## All Files Touched
            - foo.py
        """))
        write_v3_card(tmp_path, "card-01-bad-dep.md", textwrap.dedent("""\
            ---
            kind: plan-card
            card-number: 1
            card-slug: bad-dep
            ---
            ### Step 1: Bad
            - **Creates:** `foo.py`
            - **Modifies:** none
            - **Reads:** none
            - **depends-on:** [99]
            - **Commit:** `feat: bad`
        """))
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("99" in e.message or "depends-on" in e.message.lower() for e in errors)

    def test_v3_explore_not_in_reads(self, tmp_path):
        """Explore path not in Reads → BLOCKING error."""
        write_v3_overview(tmp_path, textwrap.dedent("""\
            ---
            kind: plan-overview
            task: Explore
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260415-120000
            root: ""
            ---
            ## Card Index
            ```yaml
            1:
              slug: explore-err
              creates: [foo.py]
              modifies: []
              reads: [bar.py]
              depends-on: []
            ```
            ## All Files Touched
            - foo.py
        """))
        write_v3_card(tmp_path, "card-01-explore-err.md", textwrap.dedent("""\
            ---
            kind: plan-card
            card-number: 1
            card-slug: explore-err
            ---
            ### Step 1: Explore err
            - **Creates:** `foo.py`
            - **Modifies:** none
            - **Reads:** `bar.py`
            - **Requirements:**
              - Req 1.
            - **Explore:**
              - `baz.py` — this is NOT in Reads.
            - **depends-on:** []
            - **Commit:** `feat: explore`
        """))
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("baz.py" in e.message or "Explore" in e.message for e in errors)

    def test_v3_card_index_reads_mismatch(self, tmp_path):
        """Card Index reads differs from card file Reads."""
        write_v3_overview(tmp_path, textwrap.dedent("""\
            ---
            kind: plan-overview
            task: Reads Mismatch
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260415-120000
            root: ""
            ---
            ## Card Index
            ```yaml
            1:
              slug: mismatch
              creates: [foo.py]
              modifies: []
              reads: [bar.py, baz.py]
              depends-on: []
            ```
            ## All Files Touched
            - foo.py
        """))
        # Card file Reads only has bar.py, not baz.py
        write_v3_card(tmp_path, "card-01-mismatch.md", textwrap.dedent("""\
            ---
            kind: plan-card
            card-number: 1
            card-slug: mismatch
            ---
            ### Step 1: Mismatch
            - **Creates:** `foo.py`
            - **Modifies:** none
            - **Reads:** `bar.py`
            - **depends-on:** []
            - **Commit:** `feat: mismatch`
        """))
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("reads" in e.message.lower() or "mismatch" in e.message.lower() for e in errors)

    def test_v3_overview_missing_required_key_root(self, tmp_path):
        """Overview frontmatter missing 'root' key → BLOCKING."""
        write_v3_overview(tmp_path, textwrap.dedent("""\
            ---
            kind: plan-overview
            task: No Root
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260415-120000
            ---
            ## Card Index
            ```yaml
            1:
              slug: foo
              creates: [foo.py]
              modifies: []
              reads: []
              depends-on: []
            ```
            ## All Files Touched
            - foo.py
        """))
        write_v3_card(tmp_path, "card-01-foo.md", textwrap.dedent("""\
            ---
            kind: plan-card
            card-number: 1
            card-slug: foo
            ---
            ### Step 1: Foo
            - **Creates:** `foo.py`
            - **Modifies:** none
            - **Reads:** none
            - **depends-on:** []
            - **Commit:** `feat: foo`
        """))
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("root" in e.message for e in errors)

    def test_v3_card_missing_required_frontmatter(self, tmp_path):
        """Card file missing kind/card-number/card-slug → BLOCKING."""
        write_v3_overview(tmp_path, textwrap.dedent("""\
            ---
            kind: plan-overview
            task: T
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260415-120000
            root: ""
            ---
            ## Card Index
            ```yaml
            1:
              slug: foo
              creates: [foo.py]
              modifies: []
              reads: []
              depends-on: []
            ```
            ## All Files Touched
            - foo.py
        """))
        write_v3_card(tmp_path, "card-01-foo.md", textwrap.dedent("""\
            ---
            kind: plan-card
            ---
            ### Step 1: Foo
            - **Creates:** `foo.py`
            - **Modifies:** none
            - **Reads:** none
            - **depends-on:** []
            - **Commit:** `feat: foo`
        """))
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("card-number" in e.message or "card-slug" in e.message for e in errors)

    def test_v3_missing_card_index_section(self, tmp_path):
        """Overview without ## Card Index → BLOCKING."""
        write_v3_overview(tmp_path, textwrap.dedent("""\
            ---
            kind: plan-overview
            task: No Index
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260415-120000
            root: ""
            ---
            ## All Files Touched
            - foo.py
        """))
        write_v3_card(tmp_path, "card-01-foo.md", textwrap.dedent("""\
            ---
            kind: plan-card
            card-number: 1
            card-slug: foo
            ---
            ### Step 1: Foo
            - **Creates:** `foo.py`
            - **Modifies:** none
            - **Reads:** none
            - **depends-on:** []
            - **Commit:** `feat: foo`
        """))
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("Card Index" in e.message for e in errors)

    def test_v3_creates_and_modifies_both_empty_in_index(self, tmp_path):
        """Card Index creates and modifies both empty → BLOCKING."""
        write_v3_overview(tmp_path, textwrap.dedent("""\
            ---
            kind: plan-overview
            task: Empty Write
            verify: noop
            dev-server: N/A
            approved: false
            started: 20260415-120000
            root: ""
            ---
            ## Card Index
            ```yaml
            1:
              slug: noop-card
              creates: []
              modifies: []
              reads: []
              depends-on: []
            ```
            ## All Files Touched
            - foo.py
        """))
        write_v3_card(tmp_path, "card-01-noop-card.md", textwrap.dedent("""\
            ---
            kind: plan-card
            card-number: 1
            card-slug: noop-card
            ---
            ### Step 1: Noop
            - **Creates:** none
            - **Modifies:** none
            - **Reads:** none
            - **depends-on:** []
            - **Commit:** `feat: noop`
        """))
        loc = resolve_plan_path(tmp_path)
        errors = validate(loc)
        assert any("creates" in e.message.lower() and "modifies" in e.message.lower() for e in errors)
