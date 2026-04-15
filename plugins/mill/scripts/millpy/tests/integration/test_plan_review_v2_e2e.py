"""
test_plan_review_v2_e2e.py — Integration test for v2 parallel plan-review fan-out.

Validates the full path from plan_io → spawn_reviewer CLI → engine →
plan_review_loop, using a real filesystem v2 plan directory and mocked
reviewer dispatch.

The test exercises:
1. plan_io correctly identifies a v2 plan directory.
2. plan_validator passes on a well-formed v2 plan.
3. spawn_reviewer.py CLI accepts --plan-overview and --plan-batch args.
4. PlanReviewLoop aggregates results correctly.
5. The plan_validator gate in spawn_reviewer emits ERROR JSON on BLOCKING errors.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from millpy.core.plan_io import resolve_plan_path
from millpy.core.plan_validator import validate
from millpy.core.plan_review_loop import PlanOverview, PlanReviewLoop


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

VALID_OVERVIEW = """\
    ---
    kind: plan-overview
    task: E2E Test Task
    verify: python -m pytest tests
    dev-server: N/A
    approved: false
    started: 20260415-120000
    batches: [core, extras]
    ---

    # E2E Test Task

    ## Context

    A test task for the v2 e2e integration test.

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
        summary: "Core implementation."
      extras:
        depends-on: [core]
        summary: "Extras."
    ```

    ## All Files Touched

    - plugins/mill/foo.py
    - plugins/mill/bar.py
"""

VALID_BATCH_CORE = """\
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

VALID_BATCH_EXTRAS = """\
    ---
    kind: plan-batch
    batch-name: extras
    batch-depends: [core]
    approved: false
    ---

    # Batch 02: extras

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


def write_v2_plan(tmp_path: Path) -> Path:
    """Write a complete v2 plan directory and return the task dir."""
    plan_dir = tmp_path / "task" / "plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "00-overview.md").write_text(textwrap.dedent(VALID_OVERVIEW), encoding="utf-8")
    (plan_dir / "01-core.md").write_text(textwrap.dedent(VALID_BATCH_CORE), encoding="utf-8")
    (plan_dir / "02-extras.md").write_text(textwrap.dedent(VALID_BATCH_EXTRAS), encoding="utf-8")
    return tmp_path / "task"


# ---------------------------------------------------------------------------
# Test 1: plan_io identifies v2 plan correctly
# ---------------------------------------------------------------------------

class TestPlanIoDetectsV2:
    def test_resolve_returns_v2_kind(self, tmp_path: Path):
        task_dir = write_v2_plan(tmp_path)
        loc = resolve_plan_path(task_dir)
        assert loc is not None
        assert loc.kind == "v2"

    def test_resolve_finds_both_batches(self, tmp_path: Path):
        task_dir = write_v2_plan(tmp_path)
        loc = resolve_plan_path(task_dir)
        assert loc is not None
        batch_names = [b.name for b in loc.batches]
        assert "01-core.md" in batch_names
        assert "02-extras.md" in batch_names


# ---------------------------------------------------------------------------
# Test 2: plan_validator passes on well-formed v2 plan
# ---------------------------------------------------------------------------

class TestPlanValidatorPassesV2:
    def test_valid_v2_plan_returns_no_errors(self, tmp_path: Path):
        task_dir = write_v2_plan(tmp_path)
        loc = resolve_plan_path(task_dir)
        assert loc is not None
        errors = validate(loc)
        assert errors == []


# ---------------------------------------------------------------------------
# Test 3: spawn_reviewer CLI accepts v2 plan args and validates before dispatch
# ---------------------------------------------------------------------------

class TestSpawnReviewerCliV2Args:
    def test_plan_validator_gate_blocks_invalid_plan(self, tmp_path: Path):
        """spawn_reviewer emits ERROR JSON when plan has BLOCKING validation errors."""
        import sys
        from io import StringIO
        from unittest.mock import patch

        # _run_plan_validation resolves task_dir via project_root() / "_millhouse" / "task".
        # Write the invalid plan there and mock project_root() to return tmp_path.
        plan_dir = tmp_path / "_millhouse" / "task" / "plan"
        plan_dir.mkdir(parents=True)
        (plan_dir / "00-overview.md").write_text(textwrap.dedent(VALID_OVERVIEW), encoding="utf-8")
        (plan_dir / "02-extras.md").write_text(textwrap.dedent(VALID_BATCH_EXTRAS), encoding="utf-8")
        # Corrupt the core batch: make Reads empty (triggers BLOCKING validation error)
        core_batch = plan_dir / "01-core.md"
        core_batch.write_text(textwrap.dedent("""\
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
            - **Reads:** none
            - **Requirements:**
              - Req 1.
            - **Explore:**
              - `bar.py` — pattern.
            - **depends-on:** []
            - **Commit:** `feat: add foo`
        """), encoding="utf-8")

        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("prompt\n", encoding="utf-8")

        from millpy.entrypoints.spawn_reviewer import main

        out = StringIO()
        with (
            patch("millpy.core.paths.project_root", return_value=tmp_path),
            patch("sys.stdout", out),
        ):
            exit_code = main([
                "--reviewer-name", "sonnet",
                "--prompt-file", str(prompt_file),
                "--phase", "plan",
                "--round", "1",
                "--plan-batch", str(core_batch),
            ])

        assert exit_code == 1
        output = out.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["verdict"] == "ERROR"
        assert "BLOCKING" in parsed.get("error", "") or "Reads" in parsed.get("error", "")

    def test_plan_validator_gate_passes_valid_plan(self, tmp_path: Path):
        """spawn_reviewer does not block on a valid plan (proceeds to dispatch)."""
        from io import StringIO
        from unittest.mock import MagicMock, patch

        task_dir = write_v2_plan(tmp_path)
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("prompt\n", encoding="utf-8")

        mock_result = MagicMock()
        mock_result.verdict = "APPROVE"
        mock_result.review_file = tmp_path / "review.md"

        from millpy.entrypoints.spawn_reviewer import main

        out = StringIO()
        # Patch the engine module attribute, not spawn_reviewer.run_reviewer:
        # spawn_reviewer.main() uses a lazy import ("from millpy.reviewers.engine import run_reviewer")
        # which resolves at call time, so patching the engine module attribute intercepts correctly.
        # If the import is ever hoisted to module level, change to:
        # patch("millpy.entrypoints.spawn_reviewer.run_reviewer", ...)
        with (
            patch("millpy.reviewers.engine.run_reviewer", return_value=mock_result),
            patch("sys.stdout", out),
        ):
            exit_code = main([
                "--reviewer-name", "sonnet",
                "--prompt-file", str(prompt_file),
                "--phase", "plan",
                "--round", "1",
                "--plan-batch", str(task_dir / "plan" / "01-core.md"),
            ])

        assert exit_code == 0
        output = out.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["verdict"] == "APPROVE"


# ---------------------------------------------------------------------------
# Test 4: PlanReviewLoop aggregates multi-batch results correctly
# ---------------------------------------------------------------------------

class TestPlanReviewLoopE2E:
    def test_all_slices_approve_returns_approved(self):
        loop = PlanReviewLoop(PlanOverview(batch_slugs=["core", "extras"]), max_rounds=3)
        slices = loop.next_round_plan()
        verdicts = {s: "APPROVE" for s in slices}
        outcome = loop.record_round_result(verdicts, fixer_report_path=None)
        assert outcome == "APPROVED"

    def test_one_batch_rejects_returns_continue(self, tmp_path: Path):
        loop = PlanReviewLoop(PlanOverview(batch_slugs=["core", "extras"]), max_rounds=3)
        loop.next_round_plan()
        report = tmp_path / "fix.md"
        report.write_text(
            "## Pushed Back\n### batch-extras\n- Finding 1: missing Reads\n",
            encoding="utf-8",
        )
        verdicts = {
            "batch-core": "APPROVE",
            "batch-extras": "REQUEST_CHANGES",
            "whole-plan": "APPROVE",
        }
        outcome = loop.record_round_result(verdicts, fixer_report_path=report)
        assert outcome == "CONTINUE"

    def test_non_progress_detected_across_batches(self, tmp_path: Path):
        finding = "- Step 2: design dispute"
        loop = PlanReviewLoop(PlanOverview(batch_slugs=["core", "extras"]), max_rounds=3)

        loop.next_round_plan()
        report1 = tmp_path / "fix_r1.md"
        report1.write_text(
            f"## Pushed Back\n### batch-extras\n{finding}\n### batch-core\n(empty — slice approved this round)\n",
            encoding="utf-8",
        )
        outcome1 = loop.record_round_result(
            {"batch-core": "APPROVE", "batch-extras": "REQUEST_CHANGES", "whole-plan": "APPROVE"},
            report1,
        )
        assert outcome1 == "CONTINUE"

        loop.next_round_plan()
        report2 = tmp_path / "fix_r2.md"
        report2.write_text(
            f"## Pushed Back\n### batch-extras\n{finding}\n### batch-core\n(empty — slice approved this round)\n",
            encoding="utf-8",
        )
        outcome2 = loop.record_round_result(
            {"batch-core": "APPROVE", "batch-extras": "REQUEST_CHANGES", "whole-plan": "APPROVE"},
            report2,
        )
        assert outcome2 == "BLOCKED_NON_PROGRESS"

    def test_max_rounds_exhausted(self, tmp_path: Path):
        loop = PlanReviewLoop(PlanOverview(batch_slugs=["core", "extras"]), max_rounds=2)

        loop.next_round_plan()
        report1 = tmp_path / "fix_r1.md"
        report1.write_text(
            "## Pushed Back\n### batch-core\n- Finding 1: still failing\n### batch-extras\n- Finding 2: still failing\n",
            encoding="utf-8",
        )
        outcome1 = loop.record_round_result(
            {"batch-core": "REQUEST_CHANGES", "batch-extras": "REQUEST_CHANGES", "whole-plan": "APPROVE"},
            report1,
        )
        assert outcome1 == "CONTINUE"

        loop.next_round_plan()
        report2 = tmp_path / "fix_r2.md"
        report2.write_text(
            "## Pushed Back\n### batch-core\n- Finding 1: different\n### batch-extras\n- Finding 2: different\n",
            encoding="utf-8",
        )
        outcome2 = loop.record_round_result(
            {"batch-core": "REQUEST_CHANGES", "batch-extras": "REQUEST_CHANGES", "whole-plan": "APPROVE"},
            report2,
        )
        assert outcome2 == "BLOCKED_MAX_ROUNDS"
