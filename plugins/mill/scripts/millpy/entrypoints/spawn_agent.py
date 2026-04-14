"""
entrypoints/spawn_agent.py — Unified subagent dispatch entrypoint.

Dispatches a materialized prompt file to a configured LLM backend and
emits a role-validated JSON line on stdout.

CLI flags (pythonic kebab-case):
    --role            reviewer | implementer (required)
    --prompt-file     path to materialized prompt file (required)
    --provider        WORKERS registry name (optional; falls back to
                      pipeline.implementer from _millhouse/config.yaml)
    --dispatch        tool-use | bulk (default: tool-use)
    --bulk-output     path where bulk worker stdout is saved
                      (required when --dispatch bulk)
    --max-turns       optional override; defaults: reviewer=20, implementer=200
    --work-dir        optional working directory; defaults to cwd
    --timeout         optional wall-clock timeout in seconds (default: none)

Stdout contract (single JSON line, role-dependent):
    reviewer    -> {"verdict": "...", "review_file": "..."}
    implementer -> {"phase": "...", "status_file": "...", "final_commit": "..."}

Exit codes:
    0  success, JSON line on stdout
    1  infrastructure error (backend failure, JSON parse error,
       missing prompt file, validation failure, missing --bulk-output)
    3  unknown provider (not in WORKERS registry)

Observability: every backend dispatch goes through subprocess_util.run,
which emits structured [millpy.subprocess_util] spawn/exit log lines to
stderr. The zero-PS1 assertion in D.3 reads those lines directly.
"""
from __future__ import annotations

from . import _bootstrap  # noqa: F401

import argparse
import json
import sys
from pathlib import Path


def _log(message: str) -> None:
    print(f"[millpy.spawn_agent] {message}", file=sys.stderr, flush=True)


_REVIEWER_REQUIRED_FIELDS = ("verdict", "review_file")
_IMPLEMENTER_REQUIRED_FIELDS = ("phase", "status_file", "final_commit")


def _resolve_provider_from_config() -> str | None:
    """Read pipeline.implementer from _millhouse/config.yaml. Returns None on any failure."""
    from millpy.core.config import load
    from millpy.core.paths import project_root

    try:
        root = project_root()
    except Exception:
        return None
    config_path = root / "_millhouse" / "config.yaml"
    if not config_path.exists():
        return None
    try:
        cfg = load(config_path)
    except Exception:
        return None
    pipeline = cfg.get("pipeline") if isinstance(cfg, dict) else None
    if not isinstance(pipeline, dict):
        return None
    implementer = pipeline.get("implementer")
    if isinstance(implementer, str) and implementer:
        return implementer
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spawn_agent",
        description="Dispatch a materialized prompt to a configured LLM backend.",
    )
    parser.add_argument("--role", required=True, choices=("reviewer", "implementer"))
    parser.add_argument("--prompt-file", required=True, type=Path)
    parser.add_argument("--provider", default=None)
    parser.add_argument("--dispatch", choices=("tool-use", "bulk"), default="tool-use")
    parser.add_argument("--bulk-output", type=Path, default=None)
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--work-dir", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=None)
    return parser


def _validate_role_fields(role: str, parsed: dict) -> str | None:
    """Return an error message if role-specific required fields are missing, else None."""
    required = (
        _REVIEWER_REQUIRED_FIELDS if role == "reviewer" else _IMPLEMENTER_REQUIRED_FIELDS
    )
    missing = [field for field in required if field not in parsed]
    if missing:
        return f"{role} JSON missing required field(s): {', '.join(missing)}"
    return None


def main(argv: list[str] | None = None) -> int:
    from millpy.backends import BACKENDS
    from millpy.reviewers.workers import WORKERS

    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.prompt_file.exists():
        _log(f"Prompt file not found: {args.prompt_file}")
        return 1

    provider = args.provider or _resolve_provider_from_config()
    if not provider:
        _log(
            "No provider specified. Pass --provider <name> or set "
            "pipeline.implementer in _millhouse/config.yaml."
        )
        return 1

    worker = WORKERS.get(provider)
    if worker is None:
        _log(
            f"Provider '{provider}' not implemented. "
            "Use a name from WORKERS registry (see reviewers/workers.py)."
        )
        return 3

    backend = BACKENDS.get(worker.provider)
    if backend is None:
        _log(f"Backend '{worker.provider}' not registered in BACKENDS.")
        return 3

    if args.dispatch == "bulk" and args.bulk_output is None:
        _log("--bulk-output is required when --dispatch bulk")
        return 1

    if args.max_turns is not None and args.max_turns > 0:
        max_turns = args.max_turns
    else:
        max_turns = 20 if args.role == "reviewer" else 200

    prompt_text = args.prompt_file.read_text(encoding="utf-8")

    _log(
        f"role={args.role} provider={provider} dispatch={args.dispatch} "
        f"max-turns={max_turns} prompt-file={args.prompt_file}"
    )

    if args.dispatch == "bulk":
        return _run_bulk(
            backend=backend,
            prompt_text=prompt_text,
            output_path=args.bulk_output,
            worker=worker,
            role=args.role,
        )

    return _run_tool_use(
        backend=backend,
        prompt_text=prompt_text,
        worker=worker,
        max_turns=max_turns,
        role=args.role,
    )


def _run_tool_use(*, backend, prompt_text, worker, max_turns, role) -> int:
    result = backend.dispatch_tool_use(
        prompt_text,
        model=worker.model,
        effort=worker.effort,
        max_turns=max_turns,
    )
    if result.exit_code != 0:
        _log(f"backend exited non-zero: {result.exit_code}")
        if result.raw_stderr:
            print(result.raw_stderr, file=sys.stderr)
        return 1

    if result.parsed_json is None:
        _log("backend produced no parseable JSON in result text")
        if result.raw_stderr:
            print(result.raw_stderr, file=sys.stderr)
        return 1

    parsed = result.parsed_json
    error = _validate_role_fields(role, parsed)
    if error:
        _log(error)
        return 1

    print(json.dumps(parsed, separators=(", ", ": ")))
    return 0


def _run_bulk(*, backend, prompt_text, output_path, worker, role) -> int:
    result = backend.dispatch_bulk(
        prompt_text,
        output_path,
        model=worker.model,
        effort=worker.effort,
    )
    if result.exit_code != 0:
        _log(f"backend exited non-zero: {result.exit_code}")
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return 1

    if role != "reviewer":
        _log("bulk dispatch only supported for reviewer role")
        return 1

    from millpy.core.verdict import extract_verdict_from_text

    verdict = extract_verdict_from_text(result.stdout)
    if verdict == "UNKNOWN":
        _log("bulk worker output did not contain a recognizable verdict")
        return 1

    envelope = {"verdict": verdict, "review_file": str(output_path.resolve())}
    print(json.dumps(envelope, separators=(", ", ": ")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
