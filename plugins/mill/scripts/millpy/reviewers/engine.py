"""
reviewers/engine.py — Reviewer dispatch engine.

Entry point: run_reviewer(*, reviewer_name, prompt_file, phase, round,
    review_file_path, plan_start_hash, plan_path, files_from,
    plan_overview, plan_batch, plan_dir_path)

Execution order (load-bearing for Fix E):
  1. Resolve reviewer name → ConfigError on unknown.
  2. Discussion-bulk guard → ConfigError if bulk worker + discussion phase.
  3. Plan-whole-bulk guard → ConfigError if bulk worker + plan phase + plan_dir_path set.
  4. Derive review_file_path if None (timestamp-based).
  5. mkdir _millhouse/scratch/reviews/ — ONLY after validation passes.
  6. Delegate to reviewer.run().

ConfigError is imported from millpy.core.config — the authoritative source.
"""
from __future__ import annotations

import datetime
from pathlib import Path

from millpy.core.config import ConfigError
from millpy.core.log_util import log
from millpy.core.paths import project_root
from millpy.reviewers.base import ReviewerResult, SingleWorker
from millpy.reviewers.definitions import REVIEWERS
from millpy.reviewers.ensemble import EnsembleReviewer
from millpy.reviewers.workers import WORKERS


def run_reviewer(
    *,
    reviewer_name: str,
    prompt_file: Path,
    phase: str,
    round: int,
    review_file_path: Path | None,
    plan_start_hash: str | None,
    plan_path: Path | None,
    files_from: Path | None,
    plan_overview: Path | None = None,
    plan_batch: Path | None = None,
    plan_dir_path: Path | None = None,
) -> ReviewerResult:
    """Resolve reviewer, guard, derive path, mkdir, then dispatch.

    Parameters
    ----------
    reviewer_name:
        Name of a REVIEWERS or WORKERS entry.
    prompt_file:
        Path to the review prompt file.
    phase:
        Review phase ("discussion", "plan", "code").
    round:
        Review round number (1-indexed).
    review_file_path:
        Output path for the review file. When None, the engine derives a
        timestamp-based default under _millhouse/scratch/reviews/.
    plan_start_hash:
        Git hash of the plan start commit (for diff-based file selection).
    plan_path:
        Path to the plan file (v1) or directory (v2) for PLAN_CONTENT substitution.
    files_from:
        Optional path to a file listing source files for bulk payload.
    plan_overview:
        Optional path to 00-overview.md for v2 per-batch plan review.
    plan_batch:
        Optional path to NN-<slug>.md batch file for v2 per-batch plan review.
    plan_dir_path:
        Optional path to plan/ directory for v2 whole-plan plan review.

    Returns
    -------
    ReviewerResult

    Raises
    ------
    ConfigError
        On unknown reviewer name, discussion-phase bulk guard, or
        plan-whole-plan bulk guard. All raised BEFORE any directory is
        created (Fix E).
    """
    # Step 1: Resolve reviewer name.
    reviewer = _resolve_reviewer(reviewer_name)

    # Step 2: Discussion-phase bulk guard.
    _guard_discussion_bulk(reviewer_name, reviewer, phase)

    # Step 3: Plan-whole-plan bulk guard (belt-and-suspenders).
    _guard_plan_whole_bulk(reviewer_name, reviewer, phase, plan_dir_path)

    # Step 4: Derive review_file_path if None.
    root = project_root()
    reviews_dir = root / "_millhouse" / "scratch" / "reviews"

    if review_file_path is None:
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
        review_file_path = reviews_dir / f"{ts}-{reviewer_name}-r{round}.md"

    # Step 5: Create the reviews directory (after validation succeeded).
    reviews_dir.mkdir(parents=True, exist_ok=True)
    log("engine", f"reviews dir: {reviews_dir}")

    # Step 6: Delegate to the reviewer.
    log("engine", f"dispatching {reviewer_name!r} phase={phase} round={round}")
    result = reviewer.run(
        prompt_file=prompt_file,
        phase=phase,
        round=round,
        review_file_path=review_file_path,
        files_from=files_from,
        plan_path=plan_path,
        plan_overview=plan_overview,
        plan_batch=plan_batch,
        plan_dir_path=plan_dir_path,
    )

    # Write bot-gate marker if applicable.
    if result.failure_kind == "bot-gate":
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
        marker = reviews_dir / f"{ts}-bot-gate.marker"
        try:
            marker.write_text(
                f"reviewer: {reviewer_name}\nround: {round}\n",
                encoding="utf-8",
            )
            log("engine", f"bot-gate marker written: {marker}")
        except Exception as exc:
            log("engine", f"failed to write bot-gate marker: {exc}")

    return result


def _resolve_reviewer(reviewer_name: str):
    """Resolve a reviewer name to a concrete reviewer instance.

    Resolution order (per the two-level registry decision):
      1. REVIEWERS[reviewer_name] → EnsembleReviewer
      2. WORKERS[reviewer_name]   → SingleWorker
      3. Else → ConfigError

    Parameters
    ----------
    reviewer_name:
        The name to look up.

    Returns
    -------
    EnsembleReviewer | SingleWorker
    """
    if reviewer_name in REVIEWERS:
        log("engine", f"resolved {reviewer_name!r} as EnsembleReviewer")
        return EnsembleReviewer(REVIEWERS[reviewer_name])

    if reviewer_name in WORKERS:
        log("engine", f"resolved {reviewer_name!r} as SingleWorker")
        return SingleWorker(WORKERS[reviewer_name])

    raise ConfigError(
        f"unknown reviewer: {reviewer_name!r} — not found in REVIEWERS or WORKERS"
    )


def _guard_discussion_bulk(reviewer_name: str, reviewer, phase: str) -> None:
    """Raise ConfigError if a bulk-mode worker is used in the discussion phase.

    The discussion phase has no bulk template, so bulk dispatch is forbidden.

    Parameters
    ----------
    reviewer_name:
        The reviewer name (for error messages).
    reviewer:
        The resolved reviewer instance.
    phase:
        The review phase.
    """
    if phase != "discussion":
        return

    # Determine if the reviewer uses a bulk-mode worker
    if isinstance(reviewer, SingleWorker):
        if reviewer.worker.dispatch_mode == "bulk":
            raise ConfigError(
                f"discussion phase does not support bulk dispatch: "
                f"reviewer {reviewer_name!r} has bulk-mode worker"
            )
    elif isinstance(reviewer, EnsembleReviewer):
        worker_obj = WORKERS.get(reviewer.ensemble.worker)
        if worker_obj is not None and worker_obj.dispatch_mode == "bulk":
            raise ConfigError(
                f"discussion phase does not support bulk dispatch: "
                f"reviewer {reviewer_name!r} has bulk-mode worker"
            )


def _guard_plan_whole_bulk(
    reviewer_name: str,
    reviewer,
    phase: str,
    plan_dir_path: Path | None,
) -> None:
    """Raise ConfigError if a bulk-mode worker is used for whole-plan plan review.

    Whole-plan plan review (plan_dir_path set) requires tool-use dispatch.
    Bulk workers receive a single prompt with all files inlined; they cannot
    iterate through the plan directory or call tools to read individual files.

    Parameters
    ----------
    reviewer_name:
        The reviewer name (for error messages).
    reviewer:
        The resolved reviewer instance.
    phase:
        The review phase.
    plan_dir_path:
        The plan directory path, or None for per-batch / non-plan review.
    """
    if phase != "plan" or plan_dir_path is None:
        return

    if isinstance(reviewer, SingleWorker):
        if reviewer.worker.dispatch_mode == "bulk":
            raise ConfigError(
                f"plan-review whole-plan mode does not support bulk dispatch: "
                f"reviewer {reviewer_name!r} has bulk-mode worker. "
                f"Use a tool-use reviewer for whole-plan review."
            )
    elif isinstance(reviewer, EnsembleReviewer):
        worker_obj = WORKERS.get(reviewer.ensemble.worker)
        if worker_obj is not None and worker_obj.dispatch_mode == "bulk":
            raise ConfigError(
                f"plan-review whole-plan mode does not support bulk dispatch: "
                f"reviewer {reviewer_name!r} has bulk-mode worker. "
                f"Use a tool-use reviewer for whole-plan review."
            )
