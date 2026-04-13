# Proposal 07 — Python Toolkit (Retire PowerShell Scripts)

**Status:** Proposed
**Depends on:** none
**Blocks:** none (but absorbs Proposal 02 Fix C)
**Priority:** FIRST — land before the other Proposal 02 fixes where possible.

## One-line summary

Retire the `.ps1` scripts in `plugins/mill/scripts/` in favor of a small, flat Python package. Motivated by (a) the two `[autonomous-fix]` commits in the 2026-04-13 track-child-worktree run, both PowerShell-specific JSON/string quirks, (b) the growing complexity of the scripts as Mill adds features, (c) the existing `spawn_reviewer.py` precedent showing the pattern works, and (d) a bundled fix for `mill-terminal.ps1` / `mill-vscode.ps1`, which currently open the new terminal / VSCode window in the repo root instead of the task's worktree cwd.

## Background

Mill started with PowerShell scripts because the initial target was Windows, the scripts were small, and PS was the natural choice for `git` + file templating. As Mill has grown, the scripts have grown with it — and the language is pushing back:

- `spawn-agent.ps1` now streams JSON from a `claude` subprocess and parses tool-call boundaries. Two autonomous-fix commits during the track-child-worktree run (`0461f28`, `0813108`) were both triggered by PowerShell 5 scalar-unboxing and markdown-backtick handling in the JSON path. A language with native JSON and string types would not have had either bug.
- `mill-spawn.ps1` now parses `tasks.md`, materializes handoffs, and writes structured status files. The parser regex is fragile (see Proposal 02 Fix C — absorbed by this proposal).
- The split between `spawn-agent.ps1` (PowerShell) and `spawn_reviewer.py` (Python) is already inconsistent. New features keep crossing the line. Unifying on Python ends the split.
- `mill-terminal.ps1` and `mill-vscode.ps1` open the new terminal / VSCode window with `cwd` = repo root. They should open with `cwd` = the worktree of the task they're invoked on. Small fix, but it lives in the same `.ps1` scripts that this proposal is retiring, so it's bundled here.
- The reviewer path currently builds its bulk payload from `git diff`, forcing contortions like throwaway WIP commits for comparison runs on identical content. Proposal 02 Fix G has been rewritten to require an explicit file list, not a diff — and that fix needs a git-agnostic primitive to build on. That primitive (`bulk_payload.py` or equivalent) lives in this package and is Proposal 07's responsibility.

The user has also flagged that the `spawn_reviewer.py` merge landed with ~1,490 lines of test code for ~963 lines of script — a 1.5x test-to-code ratio that was deemed overkill for a thin subprocess-dispatch module. The migration must not repeat that shape. See the Testing constraint section below; it is a load-bearing part of the proposal.

## Scope

### Migrate to Python

| Current | New (illustrative) | Notes |
|---|---|---|
| `spawn-agent.ps1` | `millpy/spawn_agent.py` | Highest risk, migrate last |
| `mill-spawn.ps1` | `millpy/spawn_task.py` | Absorbs Proposal 02 Fix C (prose parser) |
| `mill-worktree.ps1` | `millpy/worktree.py` | Pure `git worktree` wrapper |
| `mill-terminal.ps1` | `millpy/open_terminal.py` | Fix cwd bug during migration |
| `mill-vscode.ps1` | `millpy/open_vscode.py` | Fix cwd bug during migration |
| `fetch-issues.ps1` | `millpy/fetch_issues.py` | GitHub API, standalone |

### Already Python (keep)

- `_resolve.py`
- `spawn_reviewer.py`
- `spawn-reviewer.py` (shim — audit during migration; probable alias for `spawn_reviewer.py`)
- `test_spawn_reviewer.py`, `test_spawn_reviewer_integration.py` (but see Testing constraint for trimming guidance on future files of this shape)

## Library shape

A **flat** package, not a deep hierarchy. The rule: each CLI entrypoint is a short arg-parsing + dispatch module that imports from a small set of shared modules. No inheritance, no frameworks. Dataclasses for `Task`, `Worktree`, `Status` are fine. Three similar lines is better than a premature abstraction — only extract something when three call sites genuinely need it.

Illustrative modules (names and shape settled during discussion):

- `tasks_md.py` — parse and render `tasks.md`. Home for the Fix C prose-paragraph parser.
- `status_md.py` — read/write `_millhouse/task/status.md` with phase and timeline invariants.
- `claude_subprocess.py` — spawn `claude` CLI and stream/parse its JSON output. Home for the PS5 JSON quirks that triggered the two `[autonomous-fix]` commits.
- `git_ops.py` — `git -C <path>` wrappers for common worktree/branch/commit ops.
- `paths.py` — resolve parent/child worktree paths, scratch dirs, `_millhouse/` layout.
- `templates.py` — materialize `handoff.md` / brief / prompt files from templates + context.
- `bulk_payload.py` — **file-list bulker primitive for Proposal 02 Fix G.** Takes a plain list of file paths (absolute or repo-relative) and emits a bulk payload by reading each file and wrapping it in a header. **Zero git dependency** — not `git diff`, not `git show`, not `git ls-files`, nothing. The reviewer payload path and any "dump files into a prompt" path build on this primitive. A separate helper `file_list_from_diff(base, head)` is allowed to exist for the narrow case where "files of interest == files in a diff range", but it computes a plain Python list that is then fed to `bulk_payload.py` — the diff helper is never on the bulk path itself.

CLI entrypoints (one per current `.ps1` script) import from the above and contain arg parsing, a `main()`, and almost nothing else.

## Migration ordering

1. **`mill-spawn.ps1` first.** Pure file/git ops, no streaming subprocess, low blast radius. Absorbs Proposal 02 Fix C (prose parser) automatically. Validates the shape of `tasks_md.py`, `paths.py`, `templates.py`.
2. **`mill-terminal.ps1` and `mill-vscode.ps1`.** Tiny scripts (<50 LOC each). Fix the "opens in root" bug while migrating. Near-zero risk.
3. **`fetch-issues.ps1`.** Standalone, GitHub API only, no coupling to the rest.
4. **`mill-worktree.ps1`.** Mid-complexity, pure git. Validates `git_ops.py`.
5. **`spawn-agent.ps1` last.** The riskiest — it's on the critical path for every Thread B run and Proposal 05's dual-Opus orchestrator depends on it working. Migrate only after the lower-risk moves have validated the package's shape.

Each step ships independently: the plugin `.cmd` / `.ps1` wrappers (user-facing entrypoints under `.claude-plugin/`) swap their dispatch from `powershell.exe -File <x>.ps1` to `python -m millpy.<entry>` one at a time. **No big-bang cutover.**

Special care for step 5: do not migrate `spawn-agent.ps1` from inside a Thread B run that is using it (classic bootstrapping hazard). Migrate it manually, or from a fresh session that is not orchestrating another task.

## Testing constraint (load-bearing, do not relax)

The `spawn_reviewer.py` merge landed ~1,490 lines of test code for ~963 lines of script. The user has flagged this as overkill for thin glue code. For this migration the rule is:

- **Test pure logic.** Arg parsing, `tasks.md` parsing, `status.md` rendering, template materialization, path resolution — these are testable without mocks and deserve focused tests.
- **Do not test subprocess / filesystem wrappers.** `claude_subprocess.py`, `git_ops.py`, raw filesystem primitives — these are thin glue. One smoke test per entrypoint, not a suite.
- **Target ratio:** test LOC ≤ 0.5x module LOC, measured per module. If a module's tests grow larger than the module itself, the test file is pruned before merge.
- **One end-to-end smoke test** per major flow (`spawn-task → spawn-agent → spawn-reviewer`) is sufficient integration coverage. Do not build out a per-subprocess mock harness.

The goal is **correctness through narrow logic tests plus one smoke run**, not exhaustive mock coverage. This is non-negotiable in this proposal.

## Bug fix bundled into the migration — `mill-terminal` / `mill-vscode` cwd

`mill-terminal.ps1` and `mill-vscode.ps1` currently open the new terminal / VSCode window with `cwd = repo root`. Expected behavior: open with `cwd =` the worktree of the task the script was invoked for. Fix during migration by computing the target cwd from `_resolve.py` (or its Python successor) and passing it as `cwd=` to `subprocess.Popen` / the VSCode `code <path>` call.

This bug is small enough that it could be fixed standalone in the `.ps1`, but it lives inside two scripts that are being retired anyway and fixing twice is wasted work.

## Goals

- Create a Python package under `plugins/mill/scripts/` (name settled in the discussion phase — see Open questions).
- Migrate the six PowerShell scripts listed under Scope, in the order listed under Migration ordering.
- Absorb Proposal 02 Fix C (prose-paragraph parser) into the `tasks.md` parser of the new package.
- Provide `bulk_payload.py` (or equivalent) as the file-list bulker primitive required by Proposal 02 Fix G. The primitive is git-agnostic: it takes a plain list of file paths and produces a bulk payload, nothing more. A separate helper computes a file list from a git diff range **as an optional input** to the primitive — never as a replacement for it. Proposal 02 wires this primitive into the reviewer path on its side.
- Fix the `mill-terminal` / `mill-vscode` cwd bug as part of migrating those two scripts.
- Keep test LOC ≤ 0.5x script LOC across the new package. Hold the line on Testing constraint.
- Update plugin `.cmd` / `.ps1` wrappers to dispatch into `python -m <pkg>.<entry>` (or equivalent) as each script lands — step-by-step cutover, not big-bang.

## Non-goals

- A general-purpose utility library reusable outside Mill. This package is internal to Mill's scripts dir.
- Exhaustive unit-test coverage of subprocess / filesystem wrappers. See Testing constraint.
- Migrating `_millhouse/` state files or skill markdown. Text/markdown stays text/markdown.
- Retiring PowerShell on the user's machine. PowerShell is still the user's default interactive shell per global CLAUDE.md; only the Mill-internal scripts migrate.
- Adding new orchestrator features under the guise of migration. The migration is **behavior-preserving** except for the explicit bundled bug fix (mill-terminal / mill-vscode cwd) and the inherited Fix C parser correctness.

## Open questions for the discussion phase

1. **Package name.** `millpy`, `mill_py`, `mill` (clashes with the plugin dir name), `scripts` (too generic), something else? Preference: short, unambiguous in a `python -m X` context, distinct from the plugin directory.
2. **On-disk location.** `plugins/mill/scripts/<pkg>/` (keeps the scripts dir as the dispatch point) or `plugins/mill/python/<pkg>/` (new sibling dir)?
3. **Python version floor.** 3.10 (pattern matching), 3.11 (perf, better tracebacks), 3.12 (current stable)? Higher floors buy features but shrink the set of machines where Mill runs out-of-box.
4. **Dependency policy.** Stdlib-only, or allow a small number of deps like `click` / `rich` / `pydantic`? Stdlib-only keeps install trivial; a few deps would make the code more pleasant. Default leans stdlib-only.
5. **Fold `spawn_reviewer.py` into the new package, or leave it in place?** Folding gives consistency (one package holds all Python glue); leaving avoids churning a file that already works. The existing tests would need a re-home either way.
6. **Deletion cadence.** Delete each `.ps1` immediately after its Python replacement ships, or keep the `.ps1` as a fallback for a grace period?
7. **Wrapper dispatch shape.** `python -m millpy.spawn_task ...` vs `python plugins/mill/scripts/millpy/spawn_task.py ...` vs a single `mill.py` dispatcher that routes subcommands? The first is cleanest for imports; the third is more ergonomic for users reading the wrappers.
8. **`bulk_payload.py` shape.** Is it a pure function (`build_payload(paths: list[Path]) -> str`) or does it also handle per-file truncation, syntax-aware header comments, or size budgeting? Leaning toward pure and minimal — callers (Proposal 02's reviewer wiring) handle policy. But a size-budget argument is a plausible addition if reviewer prompts start hitting context limits.
9. **Where does the `git diff → file list` helper live?** In `git_ops.py` (same neighbourhood as other git wrappers, keeps `bulk_payload.py` strictly git-free), or next to `bulk_payload.py` as a sibling adapter? Leaning toward `git_ops.py` — the rule "`bulk_payload.py` has zero git imports" is easier to enforce when the diff helper physically lives elsewhere.

## Acceptance criteria

- `plugins/mill/scripts/` no longer contains `spawn-agent.ps1`, `mill-spawn.ps1`, `mill-terminal.ps1`, `mill-vscode.ps1`, `mill-worktree.ps1`, or `fetch-issues.ps1`.
- The new Python package exists under `plugins/mill/scripts/` with the six migrated entrypoints and the shared modules described under Library shape (or the shape agreed in the discussion phase).
- `bulk_payload.py` exists, accepts a plain list of file paths, and emits a bulk payload with zero direct or transitive git imports. A separate helper in `git_ops.py` computes a file list from a `git diff` range; it is invoked explicitly by callers that want diff-driven file selection, and its output is a plain `list[Path]` that feeds `bulk_payload.py` like any other list. Verified by a grep: `import git`, `subprocess.*git`, and `from git` appear zero times in `bulk_payload.py`.
- Running `mill-spawn` on a prose-paragraph `tasks.md` entry produces a `_millhouse/handoff.md` whose `## Discussion Summary` section contains the actual prose, and a `_millhouse/task/status.md` whose `task_description:` field contains the actual prose. (Proposal 02 Fix C's acceptance criterion, satisfied here instead.)
- `mill-terminal` and `mill-vscode` open their target window with `cwd` set to the worktree of the task they were invoked on, not the repo root. Verified manually on Windows against at least one child worktree.
- Test LOC across the new package is ≤ 0.5x script LOC, measured per module. Any module where the test file exceeds the module file is pruned before merge.
- One end-to-end smoke test exercises a full `spawn-task → spawn-agent → spawn-reviewer` chain without regressions.
- No regressions in existing mill skills — `mill-go`, `mill-start`, `mill-spawn`, `mill-cleanup`, `mill-merge` all still work against the migrated scripts.
- Plugin `.cmd` / `.ps1` wrappers dispatch into Python (not `powershell.exe -File`) for the migrated scripts.

## Risks and mitigations

- **Subprocess quoting on Windows.** Python's `subprocess` behaves differently from PowerShell's call operator around quoting, especially for paths with spaces. Mitigation: always use `subprocess.run([...], ...)` with a list argument (never `shell=True`), and pass `cwd=` explicitly rather than relying on inherited cwd. Audit every call site of `claude` and `git`.
- **`claude` CLI stream encoding quirks.** PS5 scalar unboxing was one symptom; there may be others that Python exposes differently (UTF-8 vs CP1252 stdout on Windows, CRLF handling in JSON lines). Mitigation: force `PYTHONIOENCODING=utf-8` in the subprocess environment and test the JSON-stream path with multi-line, empty, and error outputs.
- **Test-volume rule ignored.** An autonomous run implementing the migration may regenerate another 1.5x-sized test suite by habit. Mitigation: the rule is in Non-goals, Goals, Acceptance criteria, and the persistent `feedback_test_volume.md` memory file. Reviewer rounds should actively cut over-built test files.
- **Dependency drift.** If the package grows transitive deps, `pip install` stops being a one-liner. Mitigation: stdlib-only is the default; any proposed dep gets argued in the discussion phase.
- **Mid-migration limbo.** Five of six scripts migrated but `spawn-agent.ps1` still PowerShell, skill docs reference both worlds. Mitigation: ordering puts `spawn-agent` last and the low-risk moves first so even a partial migration ships value. Keep per-step PS1 fallbacks until each Python entry is validated.
- **Bootstrapping hazard on step 5.** Migrating `spawn-agent.ps1` from inside a Thread B run that is using it will corrupt the run. Mitigation: step 5 must be done from a fresh manual session, not inside `mill-go`.
- **Skill docs and `@mill:cli` references go stale.** The conversation/cli skill mentions PowerShell-specific tips. Mitigation: audit `plugins/mill/skills/cli/` (and neighbors) after step 5 and prune / rewrite PS-specific guidance.

## Dependencies

- None for landing.
- **Interaction with Proposal 02.** Fix C (mill-spawn.ps1 prose parser) is absorbed into this proposal and has been removed from Proposal 02's scope. Fix G (reviewer file-list bulker) is split across proposals: the `bulk_payload.py` primitive is this proposal's responsibility, the plan-format and orchestrator-wiring changes stay in Proposal 02. Fix G is only "done" when both halves are in place. The other Proposal 02 fixes (A, B, D, E, F) are independent and still apply as written. Fix D's "spawn-agent wrapper tails tool calls" implementation variant becomes strictly cleaner once `spawn-agent` is Python.
- **Interaction with Proposal 05.** The dual-Opus orchestrator rewrite depends heavily on `spawn-agent`. Landing Proposal 07 first means Proposal 05 works against Python from day one, which simplifies its own implementation.
