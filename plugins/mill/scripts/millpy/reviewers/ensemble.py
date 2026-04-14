"""
reviewers/ensemble.py — EnsembleReviewer: parallel worker dispatch.

Dispatches worker_count parallel workers via ThreadPoolExecutor, aggregates
results, and delegates final synthesis to reviewers.handler.synthesize.

Degradation rules:
  - If some workers fail but at least one succeeds, synthesize from survivors.
  - If ALL workers fail, return ReviewerResult(verdict="DEGRADED_FATAL", ...).

Bulk payload:
  When a worker's dispatch_mode == "bulk" AND files_from is passed:
    1. Load <phase>-review-bulk.md from plugins/mill/doc/prompts/.
    2. Read files_from list (one path per line).
    3. Call core.bulk_payload.build_payload and substitute at <FILES_PAYLOAD>.
    4. If the template does NOT contain <FILES_PAYLOAD>, raise ConfigError.

Handler prep (Ensemble.handler_prep=True):
  When True AND handler.dispatch_mode == "tool-use", spawn the handler prep
  pass in parallel via the same executor. Prep failure is non-fatal.
"""
from __future__ import annotations

import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Union

from millpy.backends import BACKENDS
from millpy.core import bulk_payload as bulk_payload_mod
from millpy.core.config import ConfigError
from millpy.core.log_util import log
from millpy.core.paths import project_root, repo_root
from millpy.core.verdict import extract_verdict_from_text
from millpy.reviewers.base import Ensemble, ReviewerResult, Worker
from millpy.reviewers.failures import KIND_UNCLASSIFIED, WorkerFailure
from millpy.reviewers.workers import WORKERS


# ---------------------------------------------------------------------------
# EnsembleReviewer
# ---------------------------------------------------------------------------

class EnsembleReviewer:
    """Implements the Reviewer Protocol for ensemble configurations.

    Parameters
    ----------
    ensemble:
        The Ensemble definition (worker name, count, handler name, etc.).
    """

    def __init__(self, ensemble: Ensemble) -> None:
        self.ensemble = ensemble

    def run(
        self,
        *,
        prompt_file: Path,
        phase: str,
        round: int,
        review_file_path: Path,
        files_from: Path | None,
        plan_path: Path | None = None,
    ) -> ReviewerResult:
        """Dispatch workers in parallel, aggregate results, synthesize.

        Parameters
        ----------
        prompt_file:
            Path to the review prompt file.
        phase:
            Review phase ("discussion", "plan", "code").
        round:
            Review round number (1-indexed).
        review_file_path:
            Final output path for the synthesized review.
        files_from:
            Optional path to a file listing source files for bulk payload.

        Returns
        -------
        ReviewerResult
        """
        worker_obj = WORKERS[self.ensemble.worker]
        handler_obj = WORKERS[self.ensemble.handler]

        # Materialize the prompt (bulk template substitution: payload + plan/constraints/round)
        prompt = _materialize_prompt(
            prompt_file, phase, worker_obj, files_from,
            round=round, plan_path=plan_path,
        )

        # Spawn workers in parallel
        root = project_root()
        scratch_dir = root / "_millhouse" / "scratch" / "reviews"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
        worker_count = self.ensemble.worker_count

        # Optional handler-prep pass
        prep_notes: Path | None = None
        futures: dict = {}
        prep_future = None

        with ThreadPoolExecutor(max_workers=worker_count + (1 if self.ensemble.handler_prep else 0)) as executor:
            # Submit worker tasks
            for idx in range(1, worker_count + 1):
                out_path = scratch_dir / f"{ts}-worker{idx}-r{round}.md"
                fut = executor.submit(
                    _run_worker,
                    worker=worker_obj,
                    prompt=prompt,
                    output_path=out_path,
                )
                futures[fut] = out_path

            # Submit handler prep if requested
            if self.ensemble.handler_prep and handler_obj.dispatch_mode == "tool-use":
                prep_out = scratch_dir / f"{ts}-handler-prep-r{round}.md"
                prep_future = executor.submit(
                    _run_handler_prep,
                    handler_worker=handler_obj,
                    phase=phase,
                    round=round,
                    output_path=prep_out,
                )

            # Collect worker results
            worker_results: list[Union[Path, WorkerFailure]] = []
            for fut in as_completed(futures):
                out_path = futures[fut]
                try:
                    result = fut.result()
                    worker_results.append(result)
                except Exception as exc:
                    log("ensemble", f"worker raised exception: {exc}")
                    worker_results.append(WorkerFailure(
                        kind=KIND_UNCLASSIFIED,
                        detail=str(exc),
                        exit_code=-1,
                        stderr_tail="",
                    ))

            # Collect prep notes
            if prep_future is not None:
                try:
                    prep_notes = prep_future.result()
                except Exception as exc:
                    log("ensemble", f"handler prep failed (non-fatal): {exc}")
                    prep_notes = None

        # Separate successes from failures
        successful: list[Path] = [r for r in worker_results if isinstance(r, Path)]
        failures: list[WorkerFailure] = [r for r in worker_results if isinstance(r, WorkerFailure)]

        if not successful:
            # All workers failed
            first_kind = failures[0].kind if failures else KIND_UNCLASSIFIED
            log("ensemble", f"ALL workers failed ({len(failures)} failures); kind={first_kind}")
            return ReviewerResult(
                verdict="DEGRADED_FATAL",
                review_file=review_file_path,
                exit_code=1,
                failure_kind=first_kind,
            )

        if failures:
            log(
                "ensemble",
                f"{len(failures)} worker(s) failed; continuing with {len(successful)} survivor(s)",
            )

        # Delegate to handler synthesis — handler writes directly to
        # review_file_path via its Write tool. No intermediate files, no copies.
        # Import here to avoid circular import at module level.
        from millpy.reviewers import handler as handler_mod  # noqa: PLC0415

        handler_mod.synthesize(
            successful,
            handler_obj,
            output_path=review_file_path,
            prep_notes=prep_notes,
        )

        # Extract verdict from the synthesized review. Handler output uses
        # YAML frontmatter; multi-format extraction handles it. See
        # millpy.core.verdict.
        verdict = extract_verdict_from_text(review_file_path.read_text(encoding="utf-8"))

        return ReviewerResult(
            verdict=verdict,
            review_file=review_file_path,
            exit_code=0,
            failure_kind=None,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _materialize_prompt(
    prompt_file: Path,
    phase: str,
    worker: Worker,
    files_from: Path | None,
    *,
    round: int = 1,
    plan_path: Path | None = None,
) -> str:
    """Read and optionally substitute bulk template with task context.

    If the worker uses bulk dispatch AND files_from is provided:
      1. Load <phase>-review-bulk.md template (ignores prompt_file).
      2. Build payload from listed files via bulk_payload.build_payload.
      3. Substitute <FILES_PAYLOAD>, <PLAN_CONTENT>, <CONSTRAINTS_CONTENT>, <ROUND>.
      4. Raise ConfigError if <FILES_PAYLOAD> placeholder is missing.

    Otherwise return the prompt_file contents verbatim (tool-use workers use
    --prompt-file directly; bulk+no-files_from is rare and falls through).
    """
    prompt = prompt_file.read_text(encoding="utf-8", errors="replace")

    if worker.dispatch_mode != "bulk" or files_from is None:
        return prompt

    # Load bulk template
    root = repo_root()
    template_path = root / "plugins" / "mill" / "doc" / "prompts" / f"{phase}-review-bulk.md"

    if not template_path.exists():
        log("ensemble", f"bulk template not found at {template_path}; using plain prompt")
        return prompt

    template = template_path.read_text(encoding="utf-8", errors="replace")

    placeholder = "<FILES_PAYLOAD>"
    if placeholder not in template:
        raise ConfigError(
            f"bulk template {template_path} for phase {phase} does not contain "
            f"<FILES_PAYLOAD> placeholder — cannot dispatch bulk worker for this phase"
        )

    # Read file list from files_from (one relative path per line)
    raw_paths = files_from.read_text(encoding="utf-8", errors="replace").splitlines()
    paths = [root / p.strip() for p in raw_paths if p.strip()]

    payload = bulk_payload_mod.build_payload(paths, base_dir=root)

    # Load plan content (if plan_path provided)
    if plan_path is not None and plan_path.exists():
        plan_content = plan_path.read_text(encoding="utf-8", errors="replace")
    else:
        plan_content = "(no plan available)"

    # Load CONSTRAINTS.md if present
    constraints_path = root / "CONSTRAINTS.md"
    if constraints_path.exists():
        constraints_content = constraints_path.read_text(encoding="utf-8", errors="replace")
    else:
        constraints_content = "(no CONSTRAINTS.md)"

    # Substitute all tokens. Order matters only for preventing accidental double-sub.
    return (
        template
        .replace("<FILES_PAYLOAD>", payload)
        .replace("<PLAN_CONTENT>", plan_content)
        .replace("<CONSTRAINTS_CONTENT>", constraints_content)
        .replace("<ROUND>", str(round))
    )


def _run_worker(worker: Worker, prompt: str, output_path: Path) -> Path:
    """Dispatch one worker and return the output path on success."""
    backend = BACKENDS[worker.provider]
    log("ensemble", f"spawning worker {worker.model} dispatch={worker.dispatch_mode}")

    if worker.dispatch_mode == "bulk":
        result = backend.dispatch_bulk(
            prompt,
            output_path,
            model=worker.model,
            effort=worker.effort,
        )
        if result.exit_code != 0:
            raise RuntimeError(
                f"worker exited {result.exit_code}: {result.stderr[-200:]}"
            )
        return output_path
    else:
        result = backend.dispatch_tool_use(
            prompt,
            model=worker.model,
            effort=worker.effort,
            max_turns=worker.max_turns,
        )
        if result.exit_code != 0:
            raise RuntimeError(
                f"worker exited {result.exit_code}: {result.raw_stderr[-200:]}"
            )
        if result.result_text:
            output_path.write_text(result.result_text, encoding="utf-8")
        return output_path


def _run_handler_prep(
    handler_worker: Worker,
    phase: str,
    round: int,
    output_path: Path,
) -> Path:
    """Run the handler prep pass. Returns the prep notes path."""
    root = repo_root()
    prep_template_path = root / "plugins" / "mill" / "doc" / "prompts" / "handler-prep.md"

    if not prep_template_path.exists():
        log("ensemble", f"handler-prep.md not found at {prep_template_path}; skipping prep")
        raise FileNotFoundError(str(prep_template_path))

    prep_prompt = prep_template_path.read_text(encoding="utf-8", errors="replace")
    backend = BACKENDS[handler_worker.provider]
    result = backend.dispatch_tool_use(
        prep_prompt,
        model=handler_worker.model,
        effort=handler_worker.effort,
        max_turns=handler_worker.max_turns,
    )
    if result.result_text:
        output_path.write_text(result.result_text, encoding="utf-8")
    return output_path
