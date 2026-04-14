"""
flake_gate.py — Run the millpy pytest suite N times and fail on any failure.

The zero-flake tolerance gate. Used as the final merge-gate test runner:
if any of the three runs fails, the gate blocks the merge. A one-shot
pytest pass is not enough signal for the "script doesn't return" bug
class that manifests as occasional flake before becoming hard failures.

Invocation:
    python plugins/mill/scripts/millpy/tests/scripts/flake_gate.py
    python plugins/mill/scripts/millpy/tests/scripts/flake_gate.py --runs 5
    python plugins/mill/scripts/millpy/tests/scripts/flake_gate.py --path tests/entrypoints/

The pytest suite itself is not flaky by design (all subprocess-spawning
tests use deterministic fake-subprocess fixtures). Any actual flake that
this gate catches is a real bug to investigate, not an acceptable cost.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


DEFAULT_RUNS = 3


def _resolve_default_tests_dir() -> Path:
    return Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="flake_gate",
        description="Run pytest N times consecutively; fail on any failure.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help=f"Number of consecutive pytest runs required (default {DEFAULT_RUNS}).",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Path passed to pytest. Defaults to the millpy tests directory.",
    )
    args = parser.parse_args(argv)

    tests_path = Path(args.path).resolve() if args.path else _resolve_default_tests_dir()
    if not tests_path.exists():
        print(f"[flake_gate] tests path not found: {tests_path}", file=sys.stderr)
        return 2

    print(f"[flake_gate] running pytest {args.runs} times against {tests_path}")

    for run_number in range(1, args.runs + 1):
        print(f"[flake_gate] run {run_number}/{args.runs}", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_path), "-x", "-q"],
            check=False,
        )
        if result.returncode != 0:
            print(
                f"[flake_gate] FAILED on run {run_number}/{args.runs} "
                f"(exit code {result.returncode})",
                file=sys.stderr,
            )
            return 1

    print(f"[flake_gate] PASS ({args.runs} consecutive clean runs)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
