"""
entrypoints/spawn_reviewer.py — Live reviewer entrypoint for millpy.

CLI-compatible replacement for plugins/mill/scripts/spawn_reviewer.py.
Outputs a single JSON line on stdout:
  {"verdict": "...", "review_file": "<absolute-path>"}
or on error:
  {"verdict": "ERROR", "review_file": null, "error": "<message>"}

Arguments mirror the existing spawn_reviewer.py CLI so that PS1 skill docs
and mill-go dispatch continue to work without modification.
"""
from __future__ import annotations

# sys.path fix — must be first import before any millpy.* imports
from . import _bootstrap  # noqa: F401

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    """Main entry point for spawn_reviewer.

    Parameters
    ----------
    argv:
        Argument vector. Defaults to sys.argv[1:] when None.

    Returns
    -------
    int
        Exit code (0 = success, non-zero = error).
    """
    from millpy.core.config import ConfigError, load_merged, resolve_reviewer_name
    from millpy.core.log_util import log
    from millpy.core.paths import local_config_path, mill_junction_path, project_root
    from millpy.reviewers.engine import run_reviewer

    parser = argparse.ArgumentParser(
        prog="spawn_reviewer",
        description="Dispatch a millpy reviewer and emit a JSON-line result.",
    )
    parser.add_argument(
        "--list-reviewers",
        action="store_true",
        default=False,
        help=(
            "Print the WORKERS and REVIEWERS registries and exit. "
            "Skips dispatch; other args are ignored."
        ),
    )
    parser.add_argument(
        "--reviewer-name",
        default=None,
        help=(
            "Name of a REVIEWERS or WORKERS entry. "
            "When absent, resolved from _millhouse/config.yaml using --phase and --round. "
            "Use --list-reviewers to see valid names."
        ),
    )
    parser.add_argument(
        "--prompt-file",
        default=None,
        help="Path to the review prompt file.",
    )
    parser.add_argument(
        "--phase",
        default=None,
        choices=["discussion", "plan", "code"],
        help="Review phase.",
    )
    parser.add_argument(
        "--round",
        default=None,
        type=int,
        help="Review round number (1-indexed).",
    )
    parser.add_argument(
        "--plan-start-hash",
        default=None,
        help="Git hash of the plan start commit.",
    )
    parser.add_argument(
        "--plan-path",
        default=None,
        help="Path to the plan file.",
    )
    parser.add_argument(
        "--review-file-path",
        default=None,
        help="Output path for the review file (engine derives a default when absent).",
    )
    parser.add_argument(
        "--files-from",
        default=None,
        help="Path to a file listing source files for bulk payload.",
    )
    parser.add_argument(
        "--plan-overview",
        default=None,
        help="Path to 00-overview.md for v2 per-batch plan review.",
    )
    parser.add_argument(
        "--plan-batch",
        default=None,
        help="Path to NN-<slug>.md batch file for v2 per-batch plan review.",
    )
    parser.add_argument(
        "--plan-dir-path",
        default=None,
        help="Path to plan/ directory for v2 whole-plan plan review (tool-use only).",
    )
    args = parser.parse_args(argv)

    # --list-reviewers: print registries and exit. No dispatch, no config read.
    if args.list_reviewers:
        _print_reviewer_registries()
        return 0

    # Dispatch mode: --prompt-file, --phase, --round are required.
    missing: list[str] = []
    if args.prompt_file is None:
        missing.append("--prompt-file")
    if args.phase is None:
        missing.append("--phase")
    if args.round is None:
        missing.append("--round")
    if missing:
        log("spawn_reviewer", f"missing required argument(s): {', '.join(missing)}")
        parser.error(f"missing required argument(s): {', '.join(missing)}")

    # Load config (merge .mill/config.yaml + _millhouse/config.local.yaml)
    root = project_root()
    cfg = load_merged(
        shared_path=mill_junction_path(root) / "config.yaml",
        local_path=local_config_path(root),
        legacy_path=root / "_millhouse" / "config.yaml",
    )

    # Resolve reviewer name if not provided
    reviewer_name = args.reviewer_name
    if reviewer_name is None:
        try:
            reviewer_name = resolve_reviewer_name(cfg, args.phase, args.round)
        except (ConfigError, FileNotFoundError, ValueError) as exc:
            log("spawn_reviewer", f"could not resolve reviewer name: {exc} (see --list-reviewers for valid names)")
            print(json.dumps({
                "verdict": "ERROR",
                "review_file": None,
                "error": f"{exc} (see --list-reviewers for valid names)",
            }))
            return 1

    plan_overview_path = Path(args.plan_overview) if args.plan_overview else None
    plan_batch_path = Path(args.plan_batch) if args.plan_batch else None
    plan_dir_path = Path(args.plan_dir_path) if args.plan_dir_path else None

    # plan_validator pre-dispatch gate (plan phase only)
    if args.phase == "plan":
        validation_result = _run_plan_validation(
            cfg=cfg,
            plan_path=Path(args.plan_path) if args.plan_path else None,
            plan_batch=plan_batch_path,
            plan_dir_path=plan_dir_path,
        )
        if validation_result is not None:
            log("spawn_reviewer", f"plan validation failed: {validation_result}")
            print(json.dumps({
                "verdict": "ERROR",
                "review_file": None,
                "error": validation_result,
            }))
            return 1

    # Compute canonical reviews directory: active_dir(cfg)/reviews (unified path).
    # Fall back to legacy scratch/reviews when active_dir is unavailable.
    from millpy.core.paths import active_dir
    try:
        reviews_dir = active_dir(cfg) / "reviews"
    except Exception:
        reviews_dir = root / "_millhouse" / "scratch" / "reviews"

    # Dispatch
    try:
        result = run_reviewer(
            reviewer_name=reviewer_name,
            prompt_file=Path(args.prompt_file),
            phase=args.phase,
            round=args.round,
            review_file_path=Path(args.review_file_path) if args.review_file_path else None,
            plan_start_hash=args.plan_start_hash,
            plan_path=Path(args.plan_path) if args.plan_path else None,
            files_from=Path(args.files_from) if args.files_from else None,
            plan_overview=plan_overview_path,
            plan_batch=plan_batch_path,
            plan_dir_path=plan_dir_path,
            slice_id=None,
            reviews_dir=reviews_dir,
        )
        print(json.dumps({
            "verdict": result.verdict,
            "review_file": str(result.review_file) if result.review_file else None,
        }))
        return 0

    except ConfigError as exc:
        log("spawn_reviewer", f"config error: {exc}")
        print(json.dumps({
            "verdict": "ERROR",
            "review_file": None,
            "error": str(exc),
        }))
        return 1
    except FileNotFoundError as exc:
        log("spawn_reviewer", f"file not found: {exc}")
        print(json.dumps({
            "verdict": "ERROR",
            "review_file": None,
            "error": str(exc),
        }))
        return 1
    except ValueError as exc:
        log("spawn_reviewer", f"value error: {exc}")
        print(json.dumps({
            "verdict": "ERROR",
            "review_file": None,
            "error": str(exc),
        }))
        return 1


def _run_plan_validation(
    cfg: dict,
    plan_path: Path | None,
    plan_batch: Path | None,
    plan_dir_path: Path | None,
) -> str | None:
    """Run plan_validator before dispatch. Return error string on failure, None on pass.

    task_dir is resolved via active_dir(cfg) — the wiki-based active task directory.
    Falls back to project_root()/_millhouse/task when active_dir is not available
    (pre-migration). Returns None if no plan path arg was provided (nothing to validate).

    Parameters
    ----------
    cfg:
        Merged config dict (from load_merged).
    plan_path, plan_batch, plan_dir_path:
        CLI-provided plan path args (used only to detect whether validation applies).
    """
    from millpy.core.plan_io import resolve_plan_path
    from millpy.core.plan_validator import validate

    if plan_path is None and plan_batch is None and plan_dir_path is None:
        return None

    from millpy.core.paths import active_dir, project_root
    try:
        candidate = active_dir(cfg)
        # Only use active_dir if it actually contains a plan (post-migration).
        # Fall back to the legacy _millhouse/task path otherwise.
        if resolve_plan_path(candidate) is not None:
            task_dir = candidate
        else:
            task_dir = project_root() / "_millhouse" / "task"
    except Exception:
        # Fallback for pre-migration layouts where .mill/ junction doesn't exist yet.
        task_dir = project_root() / "_millhouse" / "task"

    loc = resolve_plan_path(task_dir)
    if loc is None:
        return None

    errors = validate(loc)
    if not errors:
        return None

    blocking = [e for e in errors if e.severity == "BLOCKING"]
    if not blocking:
        return None

    lines = [f"{e.location}: {e.message}" for e in blocking]
    return f"Plan validation failed ({len(blocking)} BLOCKING error(s)):\n" + "\n".join(lines)


def _print_reviewer_registries() -> None:
    """Print both WORKERS and REVIEWERS registries to stdout for discovery."""
    from millpy.reviewers.definitions import REVIEWERS
    from millpy.reviewers.workers import WORKERS

    print("WORKERS:")
    for name in sorted(WORKERS):
        worker = WORKERS[name]
        effort = f", effort={worker.effort}" if worker.effort else ""
        print(f"  {name:20s} - provider={worker.provider} model={worker.model}{effort}")

    print()
    print("REVIEWERS:")
    for name in sorted(REVIEWERS):
        ensemble = REVIEWERS[name]
        print(
            f"  {name:36s} - worker={ensemble.worker} x{ensemble.worker_count} "
            f"handler={ensemble.handler}"
        )


if __name__ == "__main__":
    sys.exit(main())
