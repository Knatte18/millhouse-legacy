"""
reviewers/base.py — Worker, Ensemble, Reviewer Protocol, and ReviewerResult.

Worker:  atomic (provider, model, effort, dispatch_mode) configuration.
Ensemble: ensemble composition referencing WORKERS entries by name.
Reviewer: Protocol that all reviewer implementations must satisfy.
ReviewerResult: frozen result type returned by any Reviewer.run() call.
SingleWorker: simple Reviewer implementation wrapping one Worker.

Import-time validation of the registries lives in reviewers/__init__.py, not
here. This module is pure dataclasses + protocols.
"""
from __future__ import annotations

import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Protocol, runtime_checkable

from millpy.backends import BACKENDS
from millpy.core.log_util import log
from millpy.core.verdict import extract_verdict_from_text


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------

_PROVIDER_DEFAULT_DISPATCH: dict[str, str] = {
    "claude": "tool-use",
    "gemini": "bulk",
    "ollama": "tool-use",
}


@dataclass(frozen=True)
class Worker:
    """Atomic worker configuration for a single (provider, model, effort) combo.

    Fields
    ------
    provider:
        Backend provider key — must match a key in BACKENDS (checked by
        reviewers/__init__.py at import time).
    model:
        Model identifier string passed to the backend.
    effort:
        Optional effort level (claude only: "low"|"medium"|"high"|"max").
    dispatch_mode:
        "tool-use" or "bulk". If left as "" (the empty-string sentinel),
        __post_init__ fills in the per-provider default.
    max_turns:
        Tool-use turn budget. Default 30.
    extras:
        Arbitrary provider-specific key-value pairs. Wrapped in
        MappingProxyType at construction time to make it read-only.
    """

    provider: str
    model: str
    effort: str | None = None
    dispatch_mode: str = ""
    max_turns: int = 30
    extras: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Fill in per-provider default dispatch mode when left as the sentinel "".
        if self.dispatch_mode == "":
            default = _PROVIDER_DEFAULT_DISPATCH.get(self.provider, "tool-use")
            object.__setattr__(self, "dispatch_mode", default)
        # Wrap extras in MappingProxyType so callers cannot mutate it.
        object.__setattr__(self, "extras", types.MappingProxyType(dict(self.extras)))


# ---------------------------------------------------------------------------
# Ensemble
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Ensemble:
    """Ensemble composition: N parallel workers + one handler.

    Fields
    ------
    worker:
        Key in WORKERS for the parallel worker configuration.
    worker_count:
        Number of parallel worker instances. Must be >= 1.
    handler:
        Key in WORKERS for the handler (synthesis) configuration.
    handler_prep:
        When True AND handler.dispatch_mode == "tool-use", spawn a prep pass
        in parallel with the workers. Default False (no prep pass).
    """

    worker: str
    worker_count: int
    handler: str
    handler_prep: bool = False

    def __post_init__(self) -> None:
        if self.worker_count < 1:
            raise ValueError(
                f"Ensemble.worker_count must be >= 1, got {self.worker_count}"
            )


# ---------------------------------------------------------------------------
# ReviewerResult
# ---------------------------------------------------------------------------

@dataclass
class ReviewerResult:
    """Result returned by any Reviewer.run() implementation.

    Fields
    ------
    verdict:
        The review verdict string (e.g. "APPROVE", "REQUEST_CHANGES",
        "DEGRADED_FATAL").
    review_file:
        Path to the written review file.
    exit_code:
        Process exit code (0 = success).
    failure_kind:
        Failure classification if the reviewer failed, else None.
    """

    verdict: str
    review_file: Path
    exit_code: int
    failure_kind: str | None


# ---------------------------------------------------------------------------
# Reviewer Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class Reviewer(Protocol):
    """Protocol that all reviewer implementations must satisfy."""

    def run(
        self,
        *,
        prompt_file: Path,
        phase: str,
        round: int,
        review_file_path: Path,
        files_from: Path | None,
        plan_path: Path | None = None,
        plan_overview: Path | None = None,
        plan_batch: Path | None = None,
        plan_dir_path: Path | None = None,
    ) -> ReviewerResult:
        """Execute the review.

        Parameters
        ----------
        prompt_file:
            Path to the review prompt file.
        phase:
            Review phase ("discussion", "plan", "code").
        round:
            Review round number (1-indexed).
        review_file_path:
            Path where the review file should be written.
        files_from:
            Optional path to a file listing source files for bulk payload.
        plan_path:
            Optional path to the plan file — used by bulk-template substitution
            to inline plan content into `<PLAN_CONTENT>`.
        plan_overview:
            Optional path to 00-overview.md for v2 per-batch review mode.
        plan_batch:
            Optional path to NN-<slug>.md batch file for v2 per-batch review mode.
        plan_dir_path:
            Optional path to the plan/ directory for v2 whole-plan review mode.
        """
        ...


# ---------------------------------------------------------------------------
# SingleWorker
# ---------------------------------------------------------------------------

@dataclass
class SingleWorker:
    """A Reviewer that dispatches to exactly one Worker.

    Implements the Reviewer Protocol by invoking the worker's backend
    directly and writing the review file.
    """

    worker: Worker

    def run(
        self,
        *,
        prompt_file: Path,
        phase: str,
        round: int,
        review_file_path: Path,
        files_from: Path | None,
        plan_path: Path | None = None,
        plan_overview: Path | None = None,
        plan_batch: Path | None = None,
        plan_dir_path: Path | None = None,
    ) -> ReviewerResult:
        """Dispatch the review to the worker's backend.

        Reads the prompt from prompt_file, dispatches via the backend,
        writes the result to review_file_path. The plan-related kwargs
        (`plan_path`, `plan_overview`, `plan_batch`, `plan_dir_path`) are
        accepted for Protocol parity. Tool-use dispatch ignores them because
        SKILL.md already substituted the path tokens at materialization time.
        """
        prompt = prompt_file.read_text(encoding="utf-8", errors="replace")
        backend = BACKENDS[self.worker.provider]

        log("single_worker", f"dispatching {self.worker.dispatch_mode} to {self.worker.model}")

        if self.worker.dispatch_mode == "bulk":
            result = backend.dispatch_bulk(
                prompt,
                review_file_path,
                model=self.worker.model,
                effort=self.worker.effort,
            )
            output_text = result.stdout
            exit_code = result.exit_code
        else:
            result = backend.dispatch_tool_use(
                prompt,
                model=self.worker.model,
                effort=self.worker.effort,
                max_turns=self.worker.max_turns,
            )
            output_text = result.result_text
            exit_code = result.exit_code

        # Worker process failed — return ERROR, not UNKNOWN.
        if exit_code != 0:
            log("single_worker", f"worker exited non-zero: {exit_code}")
            return ReviewerResult(
                verdict="ERROR",
                review_file=review_file_path,
                exit_code=exit_code,
                failure_kind="worker_exit_nonzero",
            )

        if output_text and self.worker.dispatch_mode == "bulk":
            # Bulk workers don't write files themselves — engine writes output.
            review_file_path.write_text(output_text, encoding="utf-8")
        # Tool-use workers write their own review file via tool calls.
        # Don't duplicate their output to scratch — it creates confusing
        # dual-location files (issue #30).

        # Extract verdict from the output text. Multi-format extraction
        # recognizes YAML frontmatter, JSON last line (with optional markdown
        # fences), and the legacy VERDICT: prefix. See millpy.core.verdict.
        verdict = extract_verdict_from_text(output_text)

        # For tool-use workers, try to extract the actual review file path
        # from the agent's JSON output line (the agent writes the file itself).
        actual_review_file = review_file_path
        if self.worker.dispatch_mode == "tool-use" and output_text:
            import json as _json
            for line in reversed(output_text.strip().splitlines()):
                line = line.strip().strip("`")
                try:
                    obj = _json.loads(line)
                    if isinstance(obj, dict) and "review_file" in obj:
                        candidate = Path(obj["review_file"])
                        if candidate.exists():
                            actual_review_file = candidate
                    break
                except (ValueError, _json.JSONDecodeError):
                    continue

        return ReviewerResult(
            verdict=verdict,
            review_file=actual_review_file,
            exit_code=exit_code,
            failure_kind=None,
        )
