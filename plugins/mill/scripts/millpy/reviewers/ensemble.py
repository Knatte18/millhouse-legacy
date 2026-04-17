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
        plan_overview: Path | None = None,
        plan_batch: Path | None = None,
        plan_dir_path: Path | None = None,
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
        plan_path:
            Optional path to plan file (v1) or directory (v2) for code-review
            PLAN_CONTENT substitution.
        plan_overview:
            Optional path to 00-overview.md for v2 per-batch plan review.
        plan_batch:
            Optional path to NN-<slug>.md batch file for v2 per-batch plan review.
        plan_dir_path:
            Optional path to plan/ directory for v2 whole-plan plan review.

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
            plan_overview=plan_overview, plan_batch=plan_batch,
            plan_dir_path=plan_dir_path,
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
                    files_from=files_from,
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

        # For holistic plan-review (plan_dir_path set, no explicit files_from)
        # derive files_from from plan's `## All Files Touched` so the handler
        # has the same source-file verification basis as workers do. Filter to
        # existing files only — entries for files the plan will CREATE do not
        # yet exist on disk and would crash bulk_payload.build_payload.
        handler_files_from = files_from
        if handler_files_from is None and plan_dir_path is not None:
            try:
                from millpy.core.plan_io import resolve_plan_path, read_files_touched  # noqa: PLC0415
                from millpy.core.paths import repo_root as _repo_root  # noqa: PLC0415
                plan_loc = resolve_plan_path(plan_dir_path.parent)
                if plan_loc is not None:
                    touched = read_files_touched(plan_loc)
                    repo = _repo_root()
                    existing = [p for p in touched if (repo / p).exists() and (repo / p).is_file()]
                    if existing:
                        tmp_files_from = scratch_dir / f"{ts}-handler-files-from-r{round}.txt"
                        tmp_files_from.write_text("\n".join(existing) + "\n", encoding="utf-8")
                        handler_files_from = tmp_files_from
                        log("ensemble", f"derived handler files_from for holistic plan review: {len(existing)} files (skipped {len(touched) - len(existing)} non-existent)")
            except Exception as exc:
                log("ensemble", f"failed to derive handler files_from from plan: {exc}")

        handler_mod.synthesize(
            successful,
            handler_obj,
            output_path=review_file_path,
            prep_notes=prep_notes,
            files_from=handler_files_from,
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
    plan_overview: Path | None = None,
    plan_batch: Path | None = None,
    plan_dir_path: Path | None = None,
) -> str:
    """Read and optionally substitute bulk template with task context.

    Three-mode dispatch:

    **Tool-use workers** (dispatch_mode != "bulk"):
        Return ``prompt_file.read_text()`` verbatim. SKILL.md already
        substituted all mode tokens at materialization time.

    **Bulk workers in v2 per-batch mode** (``plan_overview`` AND ``plan_batch``
    set, ``plan_dir_path`` is None):
        Load ``plan-review-bulk.md`` template (not ``prompt_file``).
        Substitute ``<OVERVIEW_CONTENT>``, ``<BATCH_CONTENT>``,
        ``<CONSTRAINTS_CONTENT>``, ``<ROUND>``, ``<FILES_PAYLOAD>``.
        Raise ``ConfigError`` if ``<OVERVIEW_CONTENT>`` or ``<BATCH_CONTENT>``
        are missing from the template.

    **Bulk workers in v2 whole-plan mode** (``plan_dir_path`` set):
        Load ``plan-review-bulk-holistic.md`` template (added 2026-04-17).
        Concatenate all ``.md`` files in ``plan_dir_path`` as the ``<PLAN_CONTENT>``
        payload; inline source files from the plan's ``## All Files Touched`` as
        ``<FILES_PAYLOAD>``. Raises ``ConfigError`` if the template is missing or
        lacks the required placeholders.

    **Bulk workers in v1 single-file mode** (existing code-review-bulk path):
        Load ``<phase>-review-bulk.md`` template.
        Substitute ``<FILES_PAYLOAD>``, ``<PLAN_CONTENT>``,
        ``<CONSTRAINTS_CONTENT>``, ``<ROUND>``.

    ``<PLAN_CONTENT>`` v2 directory dispatch:
        If ``plan_path`` is a directory, call ``plan_io.resolve_plan_path``
        and ``plan_io.read_plan_content`` to build the concatenated v2 content.
    """
    # ------------------------------------------------------------------
    # Tool-use: return verbatim
    # ------------------------------------------------------------------
    if worker.dispatch_mode != "bulk":
        return prompt_file.read_text(encoding="utf-8", errors="replace")

    root = repo_root()

    # ------------------------------------------------------------------
    # Bulk: holistic plan-review mode (whole plan concatenated inline)
    # ------------------------------------------------------------------
    if plan_dir_path is not None:
        plan_files = sorted(plan_dir_path.glob("*.md"))
        parts: list[str] = []
        for pf in plan_files:
            content = pf.read_text(encoding="utf-8", errors="replace")
            parts.append(f"=== {pf.name} ===\n{content}")
        full_plan = "\n\n".join(parts) if parts else "(plan directory is empty)"

        template_path = root / "plugins" / "mill" / "doc" / "prompts" / "plan-review-bulk-holistic.md"
        if not template_path.exists():
            raise ConfigError(
                f"plan-review-bulk-holistic.md not found at {template_path}. "
                "Create the template before using bulk holistic plan review."
            )
        template = template_path.read_text(encoding="utf-8", errors="replace")

        if "<PLAN_CONTENT>" not in template:
            raise ConfigError(
                f"plan-review-bulk-holistic.md at {template_path} is missing "
                "<PLAN_CONTENT> placeholder"
            )
        if "<FILES_PAYLOAD>" not in template:
            raise ConfigError(
                f"plan-review-bulk-holistic.md at {template_path} is missing "
                "<FILES_PAYLOAD> placeholder"
            )

        # Build source-file FILES_PAYLOAD so bulk holistic reviewers can verify
        # plan claims against actual code. Read every path in the plan overview's
        # `## All Files Touched` section, resolve via plan_io (applies root prefix),
        # skip entries that don't exist on disk (log the skip — gap in plan).
        source_paths: list[Path] = []
        try:
            from millpy.core.plan_io import resolve_plan_path, read_files_touched  # noqa: PLC0415
            plan_loc = resolve_plan_path(plan_dir_path.parent)
            if plan_loc is not None:
                touched = read_files_touched(plan_loc)
                for rel in touched:
                    abs_path = root / rel
                    if abs_path.exists() and abs_path.is_file():
                        source_paths.append(abs_path)
                    else:
                        log("ensemble", f"holistic-bulk: skipping non-existent file from plan: {rel}")
        except Exception as exc:
            log("ensemble", f"holistic-bulk: could not resolve source files from plan: {exc}")
        if source_paths:
            files_payload = bulk_payload_mod.build_payload(source_paths, base_dir=root)
        else:
            files_payload = "(no source files in plan — holistic review cannot verify against code)"

        constraints_path = root / "CONSTRAINTS.md"
        if constraints_path.exists():
            constraints_content = constraints_path.read_text(encoding="utf-8", errors="replace")
        else:
            constraints_content = "(no CONSTRAINTS.md)"

        # One-pass regex substitution avoids recursive inflation:
        # plan content and file payload both contain placeholder mentions
        # ("substitute <FILES_PAYLOAD>", etc.) as literal prose; chained
        # .replace() calls would rewrite those too, causing 27x blowup to
        # 5 MB. Regex subn on the TEMPLATE touches each placeholder exactly
        # once and leaves substituted content's prose untouched.
        import re as _re  # noqa: PLC0415
        substitutions = {
            "<PLAN_CONTENT>": full_plan,
            "<FILES_PAYLOAD>": files_payload,
            "<CONSTRAINTS_CONTENT>": constraints_content,
            "<ROUND>": str(round),
        }
        placeholder_keys = sorted(substitutions.keys(), key=len, reverse=True)
        pattern = _re.compile("|".join(_re.escape(k) for k in placeholder_keys))
        return pattern.sub(lambda m: substitutions[m.group(0)], template)

    # ------------------------------------------------------------------
    # Bulk: v2 per-batch mode
    # ------------------------------------------------------------------
    if plan_overview is not None and plan_batch is not None:
        template_path = root / "plugins" / "mill" / "doc" / "prompts" / "plan-review-bulk.md"

        if not template_path.exists():
            raise ConfigError(
                f"plan-review-bulk.md not found at {template_path}. "
                "Create the template file before using bulk plan review."
            )

        template = template_path.read_text(encoding="utf-8", errors="replace")

        if "<OVERVIEW_CONTENT>" not in template:
            raise ConfigError(
                f"plan-review-bulk.md at {template_path} is missing "
                "<OVERVIEW_CONTENT> placeholder"
            )
        if "<BATCH_CONTENT>" not in template:
            raise ConfigError(
                f"plan-review-bulk.md at {template_path} is missing "
                "<BATCH_CONTENT> placeholder"
            )

        overview_content = plan_overview.read_text(encoding="utf-8", errors="replace")
        batch_content = plan_batch.read_text(encoding="utf-8", errors="replace")

        # Build file payload from files_from (if provided)
        if files_from is not None:
            raw_paths = files_from.read_text(encoding="utf-8", errors="replace").splitlines()
            paths = [root / p.strip() for p in raw_paths if p.strip()]
            payload = bulk_payload_mod.build_payload(paths, base_dir=root)
        else:
            payload = "(no files payload)"

        constraints_path = root / "CONSTRAINTS.md"
        if constraints_path.exists():
            constraints_content = constraints_path.read_text(encoding="utf-8", errors="replace")
        else:
            constraints_content = "(no CONSTRAINTS.md)"

        return (
            template
            .replace("<OVERVIEW_CONTENT>", overview_content)
            .replace("<BATCH_CONTENT>", batch_content)
            .replace("<CONSTRAINTS_CONTENT>", constraints_content)
            .replace("<FILES_PAYLOAD>", payload)
            .replace("<ROUND>", str(round))
        )

    # ------------------------------------------------------------------
    # Bulk: v1 single-file / code-review mode
    # ------------------------------------------------------------------
    if files_from is None:
        # No files to build payload from; fall back to plain prompt
        return prompt_file.read_text(encoding="utf-8", errors="replace")

    template_path = root / "plugins" / "mill" / "doc" / "prompts" / f"{phase}-review-bulk.md"

    if not template_path.exists():
        log("ensemble", f"bulk template not found at {template_path}; using plain prompt")
        return prompt_file.read_text(encoding="utf-8", errors="replace")

    template = template_path.read_text(encoding="utf-8", errors="replace")

    placeholder = "<FILES_PAYLOAD>"
    if placeholder not in template:
        raise ConfigError(
            f"bulk template {template_path} for phase {phase} does not contain "
            f"<FILES_PAYLOAD> placeholder — cannot dispatch bulk worker for this phase"
        )

    raw_paths = files_from.read_text(encoding="utf-8", errors="replace").splitlines()
    paths = [root / p.strip() for p in raw_paths if p.strip()]
    payload = bulk_payload_mod.build_payload(paths, base_dir=root)

    # Load plan content — supports v2 directory via plan_io
    if plan_path is not None and plan_path.exists():
        if plan_path.is_dir():
            # v2 directory: use plan_io to concatenate
            from millpy.core.plan_io import resolve_plan_path, read_plan_content  # noqa: PLC0415
            loc = resolve_plan_path(plan_path.parent)
            if loc is not None:
                plan_content = read_plan_content(loc)
            else:
                plan_content = "(plan directory found but unresolvable)"
        else:
            plan_content = plan_path.read_text(encoding="utf-8", errors="replace")
    else:
        plan_content = "(no plan available)"

    constraints_path = root / "CONSTRAINTS.md"
    if constraints_path.exists():
        constraints_content = constraints_path.read_text(encoding="utf-8", errors="replace")
    else:
        constraints_content = "(no CONSTRAINTS.md)"

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
    files_from: Path | None = None,
) -> Path:
    """Run the handler prep pass. Returns the prep notes path.

    Substitutes ``<SUBJECT>`` (from ``files_from`` list) and ``<NOTES_PATH>``
    (the output_path) in the handler-prep.md template before dispatch. The
    handler writes the prep notes to ``output_path`` via its Write tool per
    the template instructions; the engine does NOT overwrite — stdout only
    carries the PREP_DONE completion signal.
    """
    root = repo_root()
    prep_template_path = root / "plugins" / "mill" / "doc" / "prompts" / "handler-prep.md"

    if not prep_template_path.exists():
        log("ensemble", f"handler-prep.md not found at {prep_template_path}; skipping prep")
        raise FileNotFoundError(str(prep_template_path))

    prep_template = prep_template_path.read_text(encoding="utf-8", errors="replace")

    # Build <SUBJECT> substitution from files_from
    if files_from is not None and files_from.exists():
        raw_paths = files_from.read_text(encoding="utf-8", errors="replace").splitlines()
        paths = [p.strip() for p in raw_paths if p.strip()]
        subject = "\n".join(f"- {p}" for p in paths) if paths else "(no files listed)"
    else:
        subject = "(no file list provided)"

    prep_prompt = (
        prep_template
        .replace("<SUBJECT>", subject)
        .replace("<NOTES_PATH>", str(output_path))
    )

    backend = BACKENDS[handler_worker.provider]
    result = backend.dispatch_tool_use(
        prep_prompt,
        model=handler_worker.model,
        effort=handler_worker.effort,
        max_turns=handler_worker.max_turns,
    )

    if not output_path.exists():
        log("ensemble", f"handler prep did not write {output_path}; synthesis proceeds without prep notes")
    return output_path
