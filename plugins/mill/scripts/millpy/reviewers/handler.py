"""
reviewers/handler.py — Handler synthesis for ensemble reviews.

Reads the handler synthesis prompt template from
plugins/mill/doc/prompts/handler.md (relative to repo root). Substitutes
<WORKER_REPORTS>, <PREP_NOTES>, and <OUTPUT_PATH> placeholders, then dispatches
to the handler worker's backend. The handler writes its synthesis DIRECTLY to
the caller-provided output_path via its Write tool — no intermediate files,
no stdout parsing, no copy operations.

NOT unit-tested — covered by live smoke.
"""
from __future__ import annotations

from pathlib import Path

from millpy.backends import BACKENDS
from millpy.core.log_util import log
from millpy.core.paths import repo_root
from millpy.reviewers.base import Worker


def synthesize(
    worker_results: list[Path],
    handler_worker: Worker,
    output_path: Path,
    prep_notes: Path | None = None,
) -> Path:
    """Synthesize N worker review files into one consolidated review.

    Parameters
    ----------
    worker_results:
        List of paths to worker review files.
    handler_worker:
        The Worker configuration to use for synthesis.
    output_path:
        Required target path where the handler writes the synthesis directly
        via its Write tool. No intermediate files, no copies.
    prep_notes:
        Optional path to handler prep notes file.

    Returns
    -------
    Path
        The `output_path` argument, after confirming the handler wrote to it.

    Raises
    ------
    FileNotFoundError
        If the handler.md template is not found.
    RuntimeError
        If the backend failed or the handler did not write to output_path.
    """
    root = repo_root()
    template_path = root / "plugins" / "mill" / "doc" / "prompts" / "handler.md"

    if not template_path.exists():
        raise FileNotFoundError(
            f"Handler synthesis prompt template not found: {template_path}\n"
            "Create plugins/mill/doc/prompts/handler.md to enable handler synthesis."
        )

    template = template_path.read_text(encoding="utf-8", errors="replace")

    # Ensure the output directory exists (the handler's Write tool will not
    # create parent directories). The output_path itself is caller-provided.
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build the WORKER_REPORTS substitution
    report_parts: list[str] = []
    for i, report_path in enumerate(worker_results, 1):
        if report_path.exists():
            content = report_path.read_text(encoding="utf-8", errors="replace")
        else:
            content = f"(file not found: {report_path})"
        report_parts.append(f"### Worker {i}: {report_path.name}\n\n{content}")

    worker_reports_text = "\n\n---\n\n".join(report_parts)

    # Build the PREP_NOTES substitution
    if prep_notes is not None and prep_notes.exists():
        prep_notes_text = prep_notes.read_text(encoding="utf-8", errors="replace")
    else:
        prep_notes_text = "(no prep notes)"

    prompt = (
        template
        .replace("<WORKER_REPORTS>", worker_reports_text)
        .replace("<PREP_NOTES>", prep_notes_text)
        .replace("<OUTPUT_PATH>", str(output_path))
    )

    # Dispatch to backend. The handler uses its Write tool to save the synthesis
    # directly to output_path — we do NOT rely on parsing stdout for content.
    # Stdout/result_text is just a verdict signal; the review body is on disk.
    backend = BACKENDS[handler_worker.provider]
    log("handler", f"synthesizing {len(worker_results)} reports via {handler_worker.model}")

    if handler_worker.dispatch_mode == "bulk":
        result = backend.dispatch_bulk(
            prompt,
            output_path,
            model=handler_worker.model,
            effort=handler_worker.effort,
        )
        exit_code = result.exit_code
        stderr_tail = result.stderr[-500:] if result.stderr else ""
    else:
        result = backend.dispatch_tool_use(
            prompt,
            model=handler_worker.model,
            effort=handler_worker.effort,
            max_turns=handler_worker.max_turns,
        )
        exit_code = result.exit_code
        stderr_tail = result.raw_stderr[-500:] if result.raw_stderr else ""

    if exit_code != 0:
        raise RuntimeError(
            f"handler synthesis failed: {handler_worker.model} "
            f"exit={exit_code} stderr_tail={stderr_tail!r}"
        )

    # Verify the handler actually wrote the file via its Write tool.
    if not output_path.exists():
        raise RuntimeError(
            f"handler synthesis did not write output file: {handler_worker.model} "
            f"exit=0 but {output_path} does not exist. "
            f"stderr_tail={stderr_tail!r}"
        )

    file_size = output_path.stat().st_size
    if file_size == 0:
        raise RuntimeError(
            f"handler synthesis wrote empty file: {handler_worker.model} "
            f"{output_path} exists but is 0 bytes."
        )

    log("handler", f"synthesis written to {output_path} ({file_size} bytes)")
    return output_path
