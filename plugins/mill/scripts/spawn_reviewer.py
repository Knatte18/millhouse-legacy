#!/usr/bin/env python3
"""
spawn-reviewer.py — Reviewer-module engine for millhouse.

Resolves a named reviewer recipe from config, gathers files for bulk prompts,
spawns N parallel workers, synthesizes results via a handler, and emits the
standard reviewer JSON line on stdout.

Stdout: single JSON line {"verdict": "APPROVE|REQUEST_CHANGES", "review_file": "<path>"}
Stderr: informational logs with [spawn-reviewer] prefix
Exit:   0 on success, non-zero on failure
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ConfigError(Exception):
    """Raised when config.yaml schema is invalid or missing required keys."""


class BundleTooLargeError(Exception):
    """Raised when materialized prompt exceeds max-bundle-chars."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReviewerRecipe:
    name: str
    worker_model: str
    worker_count: int
    dispatch: str               # 'tool-use' or 'bulk'
    handler_model: Optional[str]
    max_bundle_chars: Optional[int]
    fallback: Optional[str]
    prompt_template: Optional[str]  # repo-relative path; required when dispatch=='bulk'
    effort: Optional[str] = None    # claude --effort: low|medium|high|max (None = CLI default)


@dataclass
class WorkerResult:
    worker_id: int
    verdict: str
    review_file: str


@dataclass
class WorkerFailure:
    kind: str   # 'rate_limit' | 'bot_gate' | 'binary_missing' | 'malformed' | 'exit_nonzero' | 'timeout'
    worker_id: int
    detail: str = ""


@dataclass
class WorkerResults:
    successes: List[WorkerResult]
    failures: List[WorkerFailure]
    bot_gated: bool
    fatal: Optional[str]
    invocation_dir: str


@dataclass
class HandlerResult:
    verdict: str
    review_file: str


# ---------------------------------------------------------------------------
# YAML hand-parser
# ---------------------------------------------------------------------------

def _coerce_scalar(value: str):
    """Coerce a bare YAML scalar string to int, bool, or str."""
    if re.match(r'^-?\d+$', value):
        return int(value)
    if value == 'true':
        return True
    if value == 'false':
        return False
    return value


def _parse_yaml(text: str) -> dict:
    """
    Hand-parse a subset of YAML sufficient for _millhouse/config.yaml:
    - Mapping nodes (key: value)
    - Nested mappings via indentation
    - Scalar nodes (string, int, bool)
    - No flow style, no anchors, no sequences (list blocks are silently skipped)

    Returns a dict. Keys are always strings.
    """
    lines = text.splitlines()
    root: dict = {}
    # Stack: list of (indent_level, dict)
    stack: list = [(0, root)]

    for raw_line in lines:
        # Skip blank lines and comment lines
        stripped = raw_line.rstrip()
        if not stripped or stripped.lstrip().startswith('#'):
            continue

        # Compute indent
        indent = len(stripped) - len(stripped.lstrip())
        content = stripped.lstrip()

        # Skip list items (not used in our config shape for now)
        if content.startswith('- ') or content == '-':
            continue

        # Must be a mapping line: key: value or key:
        if ':' not in content:
            continue

        colon_idx = content.index(':')
        key = content[:colon_idx].strip()
        rest = content[colon_idx + 1:]

        # Pop stack to the correct parent level
        while len(stack) > 1 and stack[-1][0] >= indent:
            stack.pop()

        parent = stack[-1][1]

        value_str = rest.strip()
        if value_str == '' or value_str.startswith('#'):
            # Nested mapping ahead
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            # Scalar value (strip inline comment)
            if ' #' in value_str:
                value_str = value_str[:value_str.index(' #')].strip()
            parent[key] = _coerce_scalar(value_str)

    return root


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config_from_text(yaml_text: str) -> dict:
    """Parse config from a YAML string. Tries PyYAML first, falls back to hand-parser."""
    try:
        import yaml  # type: ignore
        return yaml.safe_load(yaml_text) or {}
    except ImportError:
        return _parse_yaml(yaml_text)


def load_config(path: str) -> dict:
    """Load config from a file path."""
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    return load_config_from_text(text)


# ---------------------------------------------------------------------------
# Reviewer resolution
# ---------------------------------------------------------------------------

def resolve_reviewer(
    config: dict,
    phase: str,
    round_num: int,
    reviewer_name_override: Optional[str] = None,
) -> ReviewerRecipe:
    """
    Resolve a ReviewerRecipe from config for the given phase and round.

    Resolution order:
    1. If reviewer_name_override is supplied, use it verbatim.
    2. Else read config['review-modules'][phase].
    3. Look up str(round_num); if present, use that as reviewer name.
    4. Else use config['review-modules'][phase]['default'].
    5. Look up reviewer name in config['reviewers'][name].

    Raises ConfigError on missing keys or forbidden combinations.
    """
    # Step 1: override
    if reviewer_name_override is not None:
        reviewer_name = reviewer_name_override
    else:
        # Step 2: read review-modules
        if 'review-modules' not in config:
            raise ConfigError(
                "config schema: missing review-modules. Run 'mill-setup' to auto-migrate."
            )
        phase_cfg = config['review-modules'].get(phase)
        if phase_cfg is None:
            raise ConfigError(
                f"config schema: missing review-modules.{phase}. Run 'mill-setup' to auto-migrate."
            )

        # Step 3: round lookup
        # Normalize to string keys to handle both hand-parser (str keys)
        # and PyYAML (may parse bare integer YAML keys as int).
        phase_cfg_str = {str(k): v for k, v in phase_cfg.items()}
        round_key = str(round_num)
        if round_key in phase_cfg_str:
            reviewer_name = phase_cfg_str[round_key]
        elif 'default' in phase_cfg_str:
            reviewer_name = phase_cfg_str['default']
        else:
            raise ConfigError(
                f"config schema: missing review-modules.{phase}.default. Run 'mill-setup' to auto-migrate."
            )

    # Step 5: look up recipe
    if 'reviewers' not in config:
        raise ConfigError(
            "config schema: missing reviewers. Run 'mill-setup' to auto-migrate."
        )
    recipes = config['reviewers']
    if reviewer_name not in recipes:
        raise ConfigError(
            f"config schema: reviewer '{reviewer_name}' not found in reviewers block. Run 'mill-setup' to auto-migrate."
        )
    raw = recipes[reviewer_name]

    worker_model = raw.get('worker-model', '')
    worker_count = int(raw.get('worker-count', 1))
    dispatch = raw.get('dispatch', 'tool-use')
    handler_model = raw.get('handler-model', None)
    max_bundle_chars = raw.get('max-bundle-chars', None)
    if max_bundle_chars is not None:
        max_bundle_chars = int(max_bundle_chars)
    fallback = raw.get('fallback', None)
    prompt_template = raw.get('prompt-template', None)
    effort = raw.get('effort', None)
    if effort is not None and effort not in ('low', 'medium', 'high', 'max'):
        raise ConfigError(
            f"reviewer '{reviewer_name}': effort must be one of low|medium|high|max (got {effort!r})"
        )

    recipe = ReviewerRecipe(
        name=reviewer_name,
        worker_model=worker_model,
        worker_count=worker_count,
        dispatch=dispatch,
        handler_model=handler_model,
        max_bundle_chars=max_bundle_chars,
        fallback=fallback,
        prompt_template=prompt_template,
        effort=effort,
    )

    # Forbidden combinations
    if phase == 'discussion' and dispatch == 'bulk':
        raise ConfigError(
            "discussion-review cannot use bulk dispatch — no deterministic file scope"
        )

    if dispatch == 'tool-use' and worker_count >= 2:
        raise ConfigError(
            f"reviewer '{reviewer_name}': dispatch='tool-use' with worker-count >= 2 is not supported. "
            "Use dispatch='bulk' for multi-worker ensembles."
        )

    if dispatch == 'bulk' and prompt_template is None:
        raise ConfigError(
            f"reviewer '{reviewer_name}': dispatch='bulk' requires prompt-template"
        )

    # Fallback recipe must use tool-use dispatch (bulk fallbacks cannot be materialized
    # on the bot-gate fast-path where no bundle context is available)
    if fallback is not None:
        if fallback not in recipes:
            raise ConfigError(
                f"reviewer '{reviewer_name}': fallback '{fallback}' not found in reviewers block"
            )
        fallback_dispatch = recipes[fallback].get('dispatch', 'tool-use')
        if fallback_dispatch == 'bulk':
            raise ConfigError(
                f"reviewer '{reviewer_name}': fallback '{fallback}' uses dispatch='bulk'; "
                "fallback recipes must use dispatch='tool-use'"
            )

    return recipe


# ---------------------------------------------------------------------------
# File-scope gathering (Step 4)
# ---------------------------------------------------------------------------

def gather_file_scope(
    phase: str,
    work_dir: str,
    plan_start_hash: Optional[str] = None,
    plan_path: Optional[str] = None,
) -> List[str]:
    """
    Return repo-relative paths for the files in scope for this review phase.

    code  : git diff --name-only --diff-filter=ACMR <hash>..HEAD
    plan  : parse ## Files section from plan.md
    discussion: raises ValueError (no deterministic scope for bulk)
    """
    if phase == 'discussion':
        raise ValueError("discussion-review has no deterministic file scope for bulk dispatch")

    if phase == 'code':
        if plan_start_hash is None:
            raise ValueError("code-review requires plan_start_hash (pass --plan-start-hash)")
        result = subprocess.run(
            ['git', '-C', work_dir, 'diff', '--name-only', '--diff-filter=ACMR',
             f'{plan_start_hash}..HEAD'],
            capture_output=True, text=True,
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        return lines

    if phase == 'plan':
        if plan_path is None:
            raise ValueError("plan-review requires plan_path (pass --plan-path)")
        return _parse_plan_files_section(plan_path)

    raise ValueError(f"Unknown phase: {phase}")


def _parse_plan_files_section(plan_path: str) -> List[str]:
    """Parse bullet items from the ## Files section of a plan.md file."""
    with open(plan_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    in_files = False
    result = []
    for line in lines:
        stripped = line.rstrip()
        if stripped == '## Files':
            in_files = True
            continue
        if in_files and stripped.startswith('## '):
            break
        if in_files and (stripped.startswith('- ') or stripped.startswith('* ')):
            result.append(stripped[2:].strip())
    return result


def read_bundle_files(paths: List[str], work_dir: str) -> Dict[str, str]:
    """
    Read each file as UTF-8 and return a dict of repo-relative path -> contents.
    Raises FileNotFoundError with the offending path if a file cannot be read.
    """
    result: Dict[str, str] = {}
    for rel_path in paths:
        full_path = os.path.join(work_dir, rel_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {rel_path} (resolved to {full_path})")
        with open(full_path, 'r', encoding='utf-8') as f:
            result[rel_path] = f.read()
    return result


# ---------------------------------------------------------------------------
# Bundle materialization (Step 5)
# ---------------------------------------------------------------------------

_WORKER_PROMPT_MARKER = '## Worker Prompt'


def materialize_bulk_prompt(
    template_text: str,
    phase: str,
    file_contents: Dict[str, str],
    diff_text: str,
    plan_content: str,
    constraints_content: str,
    round_num: int,
) -> str:
    """
    Materialize the bulk prompt template by substituting all tokens.

    Tokens: <ROUND>, <DIFF>, <PLAN_CONTENT>, <CONSTRAINTS_CONTENT>, <FILE_BUNDLE>
    Unknown tokens are left as-is (not an error).

    The template file contains both human documentation (the "## Substitution
    Tokens" section) AND the executable worker prompt. The documentation
    section references the tokens by name, so a naive .replace() would
    substitute them in the docs too — duplicating the diff and file bundle
    inside the delivered prompt. We strip everything up to and including the
    '## Worker Prompt' header before substituting so only the actual worker
    prompt reaches the model.
    """
    marker_idx = template_text.find(_WORKER_PROMPT_MARKER)
    if marker_idx == -1:
        raise ValueError(
            f"bulk template missing '{_WORKER_PROMPT_MARKER}' marker; "
            "cannot safely strip documentation preamble"
        )
    worker_prompt = template_text[marker_idx + len(_WORKER_PROMPT_MARKER):].lstrip('\n')

    file_bundle = _render_file_bundle(file_contents)
    result = worker_prompt
    result = result.replace('<ROUND>', str(round_num))
    result = result.replace('<DIFF>', diff_text)
    result = result.replace('<PLAN_CONTENT>', plan_content)
    result = result.replace('<CONSTRAINTS_CONTENT>', constraints_content)
    result = result.replace('<FILE_BUNDLE>', file_bundle)
    return result


def _render_file_bundle(file_contents: Dict[str, str]) -> str:
    """Render file_contents as a sequence of ===== FILE: ... ===== blocks."""
    if not file_contents:
        return ''
    parts = []
    for path, content in file_contents.items():
        parts.append(f"===== FILE: {path} =====\n{content}\n===== END FILE: {path} =====\n")
    return '\n'.join(parts)


def enforce_bundle_size(prompt_text: str, max_bundle_chars: Optional[int]) -> None:
    """
    Raise BundleTooLargeError if prompt_text exceeds max_bundle_chars.
    If max_bundle_chars is None (tool-use recipes), no check is performed.
    """
    if max_bundle_chars is None:
        return
    size = len(prompt_text)
    if size > max_bundle_chars:
        raise BundleTooLargeError(
            f"bundle size {size} exceeds max-bundle-chars {max_bundle_chars}"
        )


# ---------------------------------------------------------------------------
# Worker dispatch (Step 6)
# ---------------------------------------------------------------------------

_SPAWN_AGENT_PATH = os.environ.get('SPAWN_AGENT_PATH', 'plugins/mill/scripts/spawn-agent.ps1')
_SPAWN_AGENT_PY_PATH = os.environ.get('SPAWN_AGENT_PY_PATH', 'plugins/mill/scripts/spawn_agent.py')

_OLLAMA_PROVIDERS = frozenset({'ollama-glm-flash', 'ollama-qwen-thinker'})


def _build_worker_cmd(
    worker_model: str,
    prompt_file: str,
    bulk_out: Optional[str],
    effort: Optional[str],
    tool_use_out: Optional[str] = None,
) -> List[str]:
    """Build the subprocess command for one worker.

    Ollama providers route to spawn_agent.py (Python). Everything else
    goes through spawn-agent.ps1 (PowerShell). Both scripts honor the
    same JSON output contract.
    """
    if worker_model in _OLLAMA_PROVIDERS:
        cmd = [
            sys.executable, _SPAWN_AGENT_PY_PATH,
            '--role', 'reviewer',
            '--provider-name', worker_model,
            '--prompt-file', prompt_file,
        ]
        if bulk_out is not None:
            cmd += ['--dispatch-mode', 'bulk', '--bulk-output-file', bulk_out]
        else:
            cmd += ['--dispatch-mode', 'tool-use']
            if tool_use_out:
                cmd += ['--bulk-output-file', tool_use_out]
        return cmd

    cmd = [
        'powershell.exe', '-File', _SPAWN_AGENT_PATH,
        '-Role', 'reviewer',
        '-ProviderName', worker_model,
        '-PromptFile', prompt_file,
    ]
    if bulk_out is not None:
        cmd += ['-DispatchMode', 'bulk', '-BulkOutputFile', bulk_out]
    if effort:
        cmd += ['-Effort', effort]
    return cmd


def dispatch_workers(
    recipe: ReviewerRecipe,
    prompt_file_path: Optional[str],
    materialized_prompt: Optional[str],
    work_dir: str,
    round_num: int,
    reviews_dir_base: str,
) -> WorkerResults:
    """
    Dispatch N workers according to recipe.dispatch.

    tool-use + worker_count==1: single synchronous subprocess call.
    bulk + worker_count>=1: write bulk prompt, spawn N workers in parallel.
    """
    ts = datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    invocation_dir = os.path.join(reviews_dir_base, ts)
    os.makedirs(invocation_dir, exist_ok=True)

    if recipe.dispatch == 'tool-use':
        if prompt_file_path is None:
            raise ValueError("tool-use dispatch requires prompt_file_path")
        return _dispatch_tool_use(recipe, prompt_file_path, invocation_dir)

    if recipe.dispatch == 'bulk':
        if materialized_prompt is None:
            raise ValueError("bulk dispatch requires materialized_prompt")
        return _dispatch_bulk(recipe, materialized_prompt, invocation_dir)

    raise ValueError(f"Unknown dispatch mode: {recipe.dispatch}")


def _dispatch_tool_use(
    recipe: ReviewerRecipe,
    prompt_file_path: str,
    invocation_dir: str,
) -> WorkerResults:
    """Dispatch a single tool-use worker synchronously."""
    tool_use_out = os.path.join(invocation_dir, 'tool-use-review.md')
    cmd = _build_worker_cmd(
        worker_model=recipe.worker_model,
        prompt_file=prompt_file_path,
        bulk_out=None,
        effort=recipe.effort,
        tool_use_out=tool_use_out,
    )
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=1800,
        )
    except subprocess.TimeoutExpired:
        failure = WorkerFailure(kind='timeout', worker_id=1, detail='subprocess timeout')
        return WorkerResults(
            successes=[], failures=[failure], bot_gated=False,
            fatal='single-worker-failed', invocation_dir=invocation_dir,
        )

    if result.returncode != 0:
        kind = _classify_exit_code(result.returncode)
        stderr_log_path = os.path.join(invocation_dir, 'worker-stderr.log')
        with open(stderr_log_path, 'w', encoding='utf-8') as f:
            f.write(result.stderr or '')
        _log(f'tool-use worker failed: exit={result.returncode} kind={kind} stderr at {stderr_log_path}')
        tail = (result.stderr or '').splitlines()[-10:]
        for line in tail:
            _log(f'  stderr: {line}')
        failure = WorkerFailure(kind=kind, worker_id=1, detail=f'exit={result.returncode}; stderr at {stderr_log_path}')
        return WorkerResults(
            successes=[], failures=[failure], bot_gated=(kind == 'bot_gate'),
            fatal='single-worker-failed', invocation_dir=invocation_dir,
        )

    parsed = _parse_json_line(result.stdout)
    if parsed is None or 'verdict' not in parsed or 'review_file' not in parsed:
        failure = WorkerFailure(kind='malformed', worker_id=1, detail=result.stdout[:200])
        return WorkerResults(
            successes=[], failures=[failure], bot_gated=False,
            fatal='single-worker-failed', invocation_dir=invocation_dir,
        )

    success = WorkerResult(worker_id=1, verdict=parsed['verdict'], review_file=parsed['review_file'])
    return WorkerResults(
        successes=[success], failures=[], bot_gated=False,
        fatal=None, invocation_dir=invocation_dir,
    )


def _dispatch_bulk(
    recipe: ReviewerRecipe,
    materialized_prompt: str,
    invocation_dir: str,
) -> WorkerResults:
    """Spawn N bulk workers in parallel, wait for all, classify failures."""
    # Write the materialized prompt once
    bulk_prompt_path = os.path.join(invocation_dir, 'bulk-prompt.md')
    with open(bulk_prompt_path, 'w', encoding='utf-8') as f:
        f.write(materialized_prompt)

    n = recipe.worker_count
    procs = []

    for i in range(1, n + 1):
        out_path = os.path.join(invocation_dir, f'r{i}.md')
        cmd = _build_worker_cmd(
            worker_model=recipe.worker_model,
            prompt_file=bulk_prompt_path,
            bulk_out=out_path,
            effort=recipe.effort,
        )
        stderr_log_path = os.path.join(invocation_dir, f'r{i}.stderr.log')
        stderr_f = open(stderr_log_path, 'wb')
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=stderr_f,
        )
        procs.append((proc, stderr_f, stderr_log_path))

    successes: List[WorkerResult] = []
    failures: List[WorkerFailure] = []
    bot_gated = False

    for i, (proc, stderr_f, stderr_log_path) in enumerate(procs, start=1):
        worker_id = i
        try:
            stdout_b, _ = proc.communicate(timeout=1800)
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
                proc.communicate()
            except Exception:
                pass
            stderr_f.close()
            failures.append(WorkerFailure(kind='timeout', worker_id=worker_id, detail=f'timeout; stderr at {stderr_log_path}'))
            continue

        stderr_f.close()
        stdout_text = stdout_b.decode('utf-8', errors='replace').strip()

        if exit_code != 0:
            kind = _classify_exit_code(exit_code)
            if kind == 'bot_gate':
                bot_gated = True
            failures.append(WorkerFailure(kind=kind, worker_id=worker_id, detail=f'exit={exit_code}; stderr at {stderr_log_path}'))
            continue

        parsed = _parse_json_line(stdout_text)
        if parsed is None or 'verdict' not in parsed or 'review_file' not in parsed:
            failures.append(WorkerFailure(kind='malformed', worker_id=worker_id, detail=f'stdout={stdout_text[:200]}; stderr at {stderr_log_path}'))
            continue

        successes.append(WorkerResult(
            worker_id=worker_id,
            verdict=parsed['verdict'],
            review_file=parsed['review_file'],
        ))

    # Fatal rule
    fatal: Optional[str] = None
    if recipe.worker_count >= 2 and len(successes) < 2:
        fatal = 'degraded-fatal'
    elif recipe.worker_count == 1 and len(successes) == 0:
        fatal = 'single-worker-failed'

    return WorkerResults(
        successes=successes,
        failures=failures,
        bot_gated=bot_gated,
        fatal=fatal,
        invocation_dir=invocation_dir,
    )


def _classify_exit_code(exit_code: int) -> str:
    """Map spawn-agent.ps1 exit code to WorkerFailure.kind."""
    return {
        10: 'rate_limit',
        11: 'bot_gate',
        12: 'binary_missing',
        13: 'exit_nonzero',
        1:  'malformed',
    }.get(exit_code, 'exit_nonzero')


def _parse_json_line(text: str) -> Optional[dict]:
    """Find and parse the last JSON object line in text."""
    text = text.strip()
    # Try the whole text first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in reversed(lines):
        if line.startswith('{') and line.endswith('}'):
            try:
                return json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
    return None


# ---------------------------------------------------------------------------
# Handler spawn (Step 7)
# ---------------------------------------------------------------------------

def spawn_handler(
    recipe: ReviewerRecipe,
    worker_results: WorkerResults,
    phase: str,
    round_num: int,
    reviews_dir: str,
    task_reviews_dir: str,
    work_dir: str,
) -> HandlerResult:
    """
    Spawn the handler agent to synthesize worker reports.

    For degenerate n=1 tool-use recipes with handler_model=None:
    skip handler spawn; return the single worker's result directly.
    """
    if recipe.handler_model is None:
        # Degenerate single-worker: emit worker result directly
        if worker_results.successes:
            w = worker_results.successes[0]
            return HandlerResult(verdict=w.verdict, review_file=w.review_file)
        # Should not happen if caller checks fatal first
        raise RuntimeError("No successful workers and no handler configured")

    # Build degradation note
    if worker_results.failures:
        lines = [f"NOTE: {len(worker_results.failures)} worker(s) dropped:"]
        for f in worker_results.failures:
            lines.append(f"  - Worker {f.worker_id}: {f.kind} — {f.detail[:80]}")
        degradation_note = '\n'.join(lines)
    else:
        degradation_note = ''

    # Worker report paths (surviving workers only)
    worker_report_paths = '\n'.join(
        os.path.abspath(w.review_file) for w in worker_results.successes
    )

    # Combined report path: <task_reviews_dir>/<ts>-<phase>-review-r<N>.md
    ts = os.path.basename(os.path.normpath(reviews_dir))
    combined_report_path = os.path.abspath(
        os.path.join(task_reviews_dir, f'{ts}-{phase}-review-r{round_num}.md')
    )
    os.makedirs(task_reviews_dir, exist_ok=True)

    # Materialize handler prompt from review-handler/SKILL.md
    skill_path = _find_skill_path(work_dir, 'review-handler/SKILL.md')
    if skill_path and os.path.exists(skill_path):
        with open(skill_path, 'r', encoding='utf-8') as f:
            skill_text = f.read()
        # Strip leading YAML frontmatter (--- ... ---)
        skill_text = _strip_frontmatter(skill_text)
    else:
        skill_text = "# Handler prompt\n(SKILL.md not found)\n"

    handler_prompt = skill_text
    handler_prompt = handler_prompt.replace('<N>', str(round_num))
    handler_prompt = handler_prompt.replace('<PHASE>', phase)
    handler_prompt = handler_prompt.replace('<WORKER_REPORT_PATHS>', worker_report_paths)
    handler_prompt = handler_prompt.replace('<COMBINED_REPORT_PATH>', combined_report_path)
    handler_prompt = handler_prompt.replace('<DEGRADATION_NOTE>', degradation_note)

    # Write handler prompt
    handler_prompt_path = os.path.join(reviews_dir, 'handler-prompt.md')
    with open(handler_prompt_path, 'w', encoding='utf-8') as f:
        f.write(handler_prompt)

    # Spawn handler via spawn-agent.ps1
    cmd = [
        'powershell.exe', '-File', _SPAWN_AGENT_PATH,
        '-Role', 'reviewer',
        '-DispatchMode', 'tool-use',
        '-ProviderName', recipe.handler_model,
        '-PromptFile', handler_prompt_path,
    ]
    if recipe.effort:
        cmd += ['-Effort', recipe.effort]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        raise RuntimeError(
            f"[spawn-reviewer] handler spawn failed (exit {result.returncode}): {result.stderr[:200]}"
        )

    parsed = _parse_json_line(result.stdout)
    if parsed is None or 'verdict' not in parsed or 'review_file' not in parsed:
        raise RuntimeError(
            f"[spawn-reviewer] handler returned malformed JSON: {result.stdout[:200]}"
        )

    return HandlerResult(verdict=parsed['verdict'], review_file=parsed['review_file'])


def _find_skill_path(work_dir: str, skill_rel: str) -> Optional[str]:
    """Try to find a skill file relative to work_dir or git root."""
    candidates = [
        os.path.join(work_dir, 'plugins', 'mill', 'skills', skill_rel),
    ]
    # Also try git root
    try:
        r = subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                           capture_output=True, text=True)
        if r.returncode == 0:
            git_root = r.stdout.strip()
            candidates.append(os.path.join(git_root, 'plugins', 'mill', 'skills', skill_rel))
    except Exception:
        pass
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _strip_frontmatter(text: str) -> str:
    """Strip leading YAML frontmatter (--- ... ---) from a file."""
    if not text.startswith('---\n'):
        return text
    end = text.find('\n---\n', 4)
    if end == -1:
        return text
    return text[end + 5:]  # skip the closing --- and newline


# ---------------------------------------------------------------------------
# Bot-gate session marker
# ---------------------------------------------------------------------------

def _bot_gate_marker_path(reviews_base: str, recipe_name: str) -> str:
    return os.path.join(reviews_base, f'bot-gated-{recipe_name}.flag')


def _check_bot_gate_marker(reviews_base: str, recipe_name: str) -> bool:
    return os.path.exists(_bot_gate_marker_path(reviews_base, recipe_name))


def _write_bot_gate_marker(reviews_base: str, recipe_name: str) -> None:
    os.makedirs(reviews_base, exist_ok=True)
    path = _bot_gate_marker_path(reviews_base, recipe_name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"bot-gated at {datetime.datetime.utcnow().isoformat()}Z\n")


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def _log(msg: str) -> None:
    print(f"[spawn-reviewer] {msg}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="spawn-reviewer.py — reviewer-module engine")
    parser.add_argument('--reviewer-name', default=None)
    parser.add_argument('--prompt-file', required=True)
    parser.add_argument('--phase', required=True, choices=['discussion', 'plan', 'code'])
    parser.add_argument('--round', type=int, required=True)
    parser.add_argument('--config', default=None)
    parser.add_argument('--work-dir', default=None)
    parser.add_argument('--plan-start-hash', default=None)
    parser.add_argument('--plan-path', default=None)
    args = parser.parse_args()

    # Resolve work_dir
    work_dir = args.work_dir or os.getcwd()

    # Resolve git root
    try:
        r = subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                           capture_output=True, text=True, cwd=work_dir)
        git_root = r.stdout.strip() if r.returncode == 0 else work_dir
    except Exception:
        git_root = work_dir

    # Resolve config path
    config_path = args.config or os.path.join(git_root, '_millhouse', 'config.yaml')

    # Load config
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        _log(f"Config file not found: {config_path}")
        sys.exit(1)

    # Resolve recipe
    try:
        recipe = resolve_reviewer(config, args.phase, args.round, args.reviewer_name)
    except ConfigError as e:
        _log(f"ConfigError: {e}")
        sys.exit(1)

    _log(f"Resolved recipe: {json.dumps({'name': recipe.name, 'dispatch': recipe.dispatch, 'worker_count': recipe.worker_count})}")

    reviews_dir_base = os.path.join(git_root, '_millhouse', 'scratch', 'reviews')
    task_reviews_dir = os.path.join(git_root, '_millhouse', 'task', 'reviews')

    # Check for pre-existing bot-gate marker
    active_recipe = recipe
    if _check_bot_gate_marker(reviews_dir_base, recipe.name):
        if recipe.fallback:
            _log(f"Session bot-gate marker found for '{recipe.name}', switching to fallback '{recipe.fallback}'")
            try:
                active_recipe = resolve_reviewer(config, args.phase, args.round,
                                                  reviewer_name_override=recipe.fallback)
            except ConfigError as e:
                _log(f"ConfigError resolving fallback: {e}")
                sys.exit(1)
        else:
            _log(f"Session bot-gate marker found for '{recipe.name}' and no fallback configured — escalating")
            sys.exit(1)

    result = _run_recipe(
        active_recipe, args, config, git_root, work_dir,
        reviews_dir_base, task_reviews_dir,
    )

    print(json.dumps({'verdict': result.verdict, 'review_file': result.review_file}))


def _run_recipe(
    recipe: ReviewerRecipe,
    args,
    config: dict,
    git_root: str,
    work_dir: str,
    reviews_dir_base: str,
    task_reviews_dir: str,
) -> HandlerResult:
    """Core dispatch+handler pipeline for one recipe."""

    # Build materialized_prompt for bulk dispatch
    materialized_prompt = None
    if recipe.dispatch == 'bulk':
        # Gather file scope
        plan_path = args.plan_path or os.path.join(git_root, '_millhouse', 'task', 'plan.md')
        file_paths = gather_file_scope(
            args.phase, work_dir,
            plan_start_hash=args.plan_start_hash,
            plan_path=plan_path,
        )
        file_contents = read_bundle_files(file_paths, work_dir)

        # Read template
        template_path = os.path.join(git_root, recipe.prompt_template)
        with open(template_path, 'r', encoding='utf-8') as f:
            template_text = f.read()

        # diff_text for code-review
        diff_text = ''
        if args.phase == 'code' and args.plan_start_hash:
            r = subprocess.run(
                ['git', '-C', work_dir, 'diff', f'{args.plan_start_hash}..HEAD'],
                capture_output=True, text=True,
            )
            diff_text = r.stdout

        # plan_content (plan_path already resolved above for file-scope gathering)
        plan_content = ''
        if os.path.exists(plan_path):
            with open(plan_path, 'r', encoding='utf-8') as f:
                plan_content = f.read()

        # constraints_content
        constraints_path = os.path.join(git_root, 'CONSTRAINTS.md')
        if os.path.exists(constraints_path):
            with open(constraints_path, 'r', encoding='utf-8') as f:
                constraints_content = f.read()
        else:
            constraints_content = '(no CONSTRAINTS.md)'

        materialized_prompt = materialize_bulk_prompt(
            template_text, args.phase, file_contents,
            diff_text, plan_content, constraints_content, args.round,
        )
        enforce_bundle_size(materialized_prompt, recipe.max_bundle_chars)

    # Dispatch workers
    worker_results = dispatch_workers(
        recipe=recipe,
        prompt_file_path=args.prompt_file if recipe.dispatch == 'tool-use' else None,
        materialized_prompt=materialized_prompt,
        work_dir=work_dir,
        round_num=args.round,
        reviews_dir_base=reviews_dir_base,
    )

    # Handle bot-gate
    if worker_results.bot_gated:
        _write_bot_gate_marker(reviews_dir_base, recipe.name)
        if recipe.fallback:
            _log(f"Bot-gate detected, switching to fallback '{recipe.fallback}'")
            try:
                fallback_recipe = resolve_reviewer(
                    config, args.phase, args.round,
                    reviewer_name_override=recipe.fallback,
                )
            except ConfigError as e:
                _log(f"ConfigError resolving fallback: {e}")
                sys.exit(1)
            worker_results = dispatch_workers(
                recipe=fallback_recipe,
                prompt_file_path=args.prompt_file if fallback_recipe.dispatch == 'tool-use' else None,
                materialized_prompt=None,  # fallback is always tool-use
                work_dir=work_dir,
                round_num=args.round,
                reviews_dir_base=reviews_dir_base,
            )
            recipe = fallback_recipe
        else:
            _log(f"recipe '{recipe.name}' is bot-gated and has no fallback configured — escalating")
            sys.exit(1)

    # Fatal check
    if worker_results.fatal:
        _log(f"degraded-fatal: {worker_results.fatal} — {len(worker_results.successes)} successful workers")
        sys.exit(1)

    # Spawn handler (or return solo worker result)
    handler_result = spawn_handler(
        recipe=recipe,
        worker_results=worker_results,
        phase=args.phase,
        round_num=args.round,
        reviews_dir=worker_results.invocation_dir,
        task_reviews_dir=task_reviews_dir,
        work_dir=work_dir,
    )

    return handler_result


if __name__ == '__main__':
    main()
