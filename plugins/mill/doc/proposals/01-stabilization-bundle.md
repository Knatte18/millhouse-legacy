# Proposal 01 — Stabilization Bundle: Finish Python Migration, Path/Verdict Fixes, Heavy Testing

**Status:** Proposed
**Worktree:** W1 — ships as one v1 plan
**Depends on:** none
**Blocks:** W2, W3 (both assume a Python-only skill surface)

## One-line summary

Finish the Python toolkit migration that the millpy task left half-done — every mill skill calls Python entrypoints, not PowerShell — and land the eight outstanding stabilization fixes inside the same worktree, plus a heavy testing regime so the class of "script doesn't return" bugs cannot recur silently. One bundle, one worktree, one merge. Reviewer pipeline was the only piece flipped during millpy; the rest has been drifting on PS1 shims ever since, and most outstanding bug reports touch code that is about to be rewritten anyway — patching PS1 first and porting second is wasted work.

## Context — how we know this has to happen together

Two observations from the last 24 hours forced this bundling:

1. **The millpy task landed the `millpy` package but only flipped the reviewer pipeline.** Today's skills reference seven different PS1 files (`mill-spawn.ps1`, `mill-terminal.ps1`, `mill-vscode.ps1`, `mill-worktree.ps1`, `fetch-issues.ps1`, `spawn-agent.ps1`, plus some internal helpers). Python equivalents exist on disk for all of them except `spawn-agent.ps1`, but nothing actually calls them. It's the classic half-migration, and every new fix that touches one of these scripts has to be written twice if we don't finish the migration first.

2. **An external bug report filed nine concrete bugs.** Seven came from running mill in a nested-project layout (`c:/Code/py/projects/piprocessing/`), two are carry-over from earlier runs. Every bug that touches `spawn-agent.ps1` or `mill-setup`'s shell-level config writing needs to happen in the Python version, not the PS1 version, because the PS1 version is getting deleted. Several of the bugs are actually "the new Python layout fixes them for free" once the migration is done.

**Heavy testing is a first-class deliverable of this worktree.** The user's pain point is explicit: "Det har vært for mye bugs i disse scriptene allerede: review-spawner som ikke returnerer, og slikt tull." Script migration without testing is script migration that ships the same bug class in a new language. The testing in Part D is part of the acceptance gate, not a nice-to-have.

---

## Part A — Finish the Python toolkit migration

### A.1 — Port `spawn-agent.ps1` fully to Python

**Why fully, not a thin wrapper.** The PS1 version has been the biggest source of script bugs (reviewer spawner not returning, markdown-wrapped JSON causing parse failures, subprocess contract drift). A thin Python wrapper around the PS1 would preserve those bugs unchanged. A full Python port makes the subprocess contract auditable and testable in one language.

**Responsibilities of the new `millpy/entrypoints/spawn_agent.py`:**

1. Accept CLI flags equivalent to the PS1 original (`-Role` → `--role`, `-Prompt` → `--prompt`, `-PromptFile` → `--prompt-file`, `-MaxTurns` → `--max-turns`, `-Model` → `--model`, etc.).
2. Resolve the `claude` CLI binary via PATH. If not found, exit non-zero with a clear error naming the missing dependency.
3. Launch `claude` as a subprocess with explicit `encoding='utf-8'`, `errors='replace'`, stdin/stdout piped, a configurable timeout, and a hard ceiling on wall-clock time.
4. Block until the subprocess returns. If the child has not returned within the timeout, kill it and exit non-zero with a clear "subprocess timeout" error. **Never exit zero on an unreturned subprocess.**
5. Parse stdout for the JSON line. Strip markdown code fences (both `` `...` `` and ``` ```...``` ```) and leading/trailing whitespace before `json.loads`. The stripping logic lives in `millpy/core/verdict.py` as a shared helper used by both `spawn_agent.py` and `spawn_reviewer.py`.
6. Return the parsed JSON as the process's exit stdout, and the exit code from the child (or a synthesized code if the JSON says `verdict: REQUEST_CHANGES`, etc.).

**Plugin-cache resolution is a non-issue in the new layout.** The old bug was "spawn-agent.ps1 path is hardcoded relative to git root, breaks when mill plugin lives outside the working repo". The new `spawn_agent.py` is itself a Python module under `plugins/mill/scripts/millpy/`, resolved via the same three-tier lookup as every other Python entrypoint. The bug cannot exist in the new layout.

### A.2 — Migrate `mill-setup` to a Python entrypoint

The heaviest skill to flip. Today's `mill-setup/SKILL.md` references 7 PS1 files and embeds shell-level logic for copying forwarding wrappers, writing `_millhouse/config.yaml`, creating the `_millhouse/` directory tree, and validating the plugin cache junction.

**New entrypoint: `millpy/entrypoints/setup.py`.**

Responsibilities:

1. Create the `_millhouse/` directory structure on a fresh clone. Idempotent on re-run — skip what already exists, warn about drift.
2. Write `_millhouse/config.yaml` from a template, **with correct reviewer names from day one**. Short ensemble names (`g3flash-x3-sonnetmax` and siblings), no Pro-based entries, no dead `reviewers:` block, no duplicate `models:<phase>-review.default` slots. Just `review-modules:` with the new names.
3. Rename the REVIEWERS registry in `millpy/reviewers/definitions.py` (or wherever the registry lives) to short form: `ensemble-gemini3flash-x3-sonnetmax` → `g3flash-x3-sonnetmax`. Drop Pro-based ensembles from the default set — the pipeline standardizes on Gemini Flash (`gemini-3-flash-preview`) as the sole Gemini tier. Keep `resolve_reviewer_name`'s legacy fallback path for hand-written configs from before the rename, but stop producing legacy names on fresh installs.
4. Write `_millhouse/*` forwarding wrappers as Python shims (or remove the pattern entirely if migration makes it unnecessary). The goal is that nothing in `_millhouse/` references a PS1 file.
5. Validate the plugin cache junction at `~/.claude/plugins/cache/millhouse/mill/<ver>/`. If the target is missing or dangling, report a clear error with the `symlink-plugins.ps1` repair command. (Automated repair is deferred — error reporting first.)
6. Exit cleanly with a human-readable summary of what was created, skipped, and warned about.

**`mill-setup/SKILL.md` becomes a thin wrapper** that calls `python plugins/mill/scripts/setup.py` once and presents the output to the user. No embedded shell logic.

### A.3 — Flip remaining skills to Python entrypoints

Small edits per skill. Each skill's `SKILL.md` text is updated to call the matching Python entrypoint instead of the PS1 script.

| Skill | Change |
|---|---|
| `mill-spawn` | Replace `mill-spawn.ps1` call with `python plugins/mill/scripts/spawn-task.py`. Replace `mill-worktree.ps1` call with `python plugins/mill/scripts/worktree.py`. |
| `mill-go` | Replace `mill-spawn.ps1` call. Replace `spawn-agent.ps1` call with `python plugins/mill/scripts/spawn-agent.py` from A.1. |
| `mill-inbox` | Replace `fetch-issues.ps1` with `python plugins/mill/scripts/fetch-issues.py`. |
| `mill-setup` | See A.2. |
| `mill-start` | No changes — already Python-only via `spawn-reviewer.py`. |
| Everything else in `plugins/mill/skills/` | Grep each `SKILL.md` for `.ps1` references and flip. The inventory above is the known set; the grep catches anything missed. |

**Acceptance gate for A.3:** `grep -rE '\.ps1' plugins/mill/skills/` returns zero matches.

### A.4 — Delete obsolete PS1 files

After A.1-A.3 land AND Part D's parity tests pass, delete:

- `plugins/mill/scripts/mill-spawn.ps1`
- `plugins/mill/scripts/mill-worktree.ps1`
- `plugins/mill/scripts/mill-terminal.ps1`
- `plugins/mill/scripts/mill-vscode.ps1`
- `plugins/mill/scripts/fetch-issues.ps1`
- `plugins/mill/scripts/spawn-agent.ps1`

`plugins/mill/scripts/spawn_reviewer.py` and `plugins/mill/scripts/spawn-reviewer.py` (the two existing shims) stay as-is — they already forward to `millpy.entrypoints.spawn_reviewer`.

---

## Part B — Fix path resolution, config, and verdict parsing

These fixes live in Python code — either in modules A.1-A.2 write from scratch, or in `spawn_reviewer.py` / engine code that was already Python. The shared helper `millpy/core/verdict.py` from A.1 is used by both.

### B.1 — `spawn_reviewer.py` assumes git root equals project root (nested-project path resolution)

The external bug report (#4) filed: in a layout where git root is `c:/Code/py` and project root is `c:/Code/py/projects/piprocessing/`, `spawn_reviewer.py` looks for `_millhouse/config.yaml` at git root and fails. Default reviews directory logs `C:\Code\py\_millhouse\scratch\reviews` (git root, wrong place). Worker stdout JSON wrapper files land at the git-root `_millhouse/scratch/reviews/` instead of the project's.

**The fix.** Add a `--project-root` (or `--millhouse-dir`) flag to `spawn_reviewer.py`. When absent, auto-detect by walking up from the current working directory looking for a `_millhouse/` directory — stop at the first one found, or at git root, whichever comes first.

**Scope of the walk-up.** Every call to `repo_root()` in `millpy/` for mill-state paths is routed through a new `project_root()` resolver in `millpy/core/paths.py`. Grep for `repo_root()` callers and audit each — some (e.g. source-file lookups) do want git root, others (mill-state) want project root.

**Acceptance:** running `spawn_reviewer.py` from inside `c:/Code/py/projects/piprocessing/` finds `_millhouse/config.yaml` at `projects/piprocessing/_millhouse/config.yaml`, not at the git root. Explicit `--project-root` override also works. Cross-layout tests in D.2 cover this.

### B.2 — Engine reports `UNKNOWN` verdict on valid worker output (shared verdict helper)

The external bug report (#6) filed: worker's `claude` CLI result sometimes comes back wrapped in markdown code fences (`` `{"verdict": "APPROVE", ...}` ``). The engine's verdict-extraction regex does not strip the fences before `json.loads`, so parsing fails and it reports `verdict: UNKNOWN` upstream. The underlying review markdown file is written correctly; only the verdict return path is broken.

Observed three times in one session (discussion review r1, code review r1, plan review r1).

**The fix.** `millpy/core/verdict.py` exposes a `parse_verdict_line(raw: str) -> dict` helper that:

1. Strips leading/trailing whitespace.
2. Strips surrounding markdown code fences — both `` `...` `` and ``` ```[lang?]...``` ``` variants.
3. Parses the stripped content as JSON.
4. Returns the parsed dict, or raises a typed `VerdictParseError` with the original raw string for diagnostics.

Both `millpy/entrypoints/spawn_agent.py` (A.1) and `millpy/entrypoints/spawn_reviewer.py` use the helper. The reviewer engine's verdict extraction is also rewired to go through it.

Also: tighten the worker prompt template to say "no markdown formatting on the JSON line" — belt and suspenders.

**Acceptance:** three unit tests cover `` `X` ``, ``` ```X``` ```, and ``` ```json\nX\n``` ``` wrappings. End-to-end runs parse wrapped verdicts correctly.

### B.3 — `spawn_reviewer.py --list-reviewers` for discoverability

The external bug report (#7) filed: passing `--reviewer-name sonnet` is the only way to bypass config resolution, but there is no way to discover what names are valid without grepping `millpy/reviewers/workers.py` and `definitions.py`. The `unknown reviewer` error message does not list valid options.

**The fix.** Add `python spawn_reviewer.py --list-reviewers` that prints both registries (WORKERS + REVIEWERS) to stdout, one section per registry, one name per line, with a short description if available. Reference the flag in the `unknown reviewer` error message: `unknown reviewer: 'foo' — see --list-reviewers for valid names`.

**Acceptance:** running `spawn_reviewer.py --list-reviewers` prints both registries; an invalid `--reviewer-name` produces an error mentioning `--list-reviewers`.

---

## Part C — Skill-text policy fixes

These are content changes in `SKILL.md` files. No Python code involved.

### C.1 — Worktree isolation rule in the conversation skill

During the 2026-04-13 track-child-worktree run, Phase: Setup ran `cd <parent-path> && git commit`, which corrupted the shell cwd for the rest of the session. Subsequent commands operated on the parent worktree instead of the child, with cascading failures (Thread B spawn fired against parent's `spawn-agent.ps1`, brief materialization landed in parent's scratch directory, etc.). The deeper issue is not `cd` vs `git -C` — it is that the orchestrator was reaching into the parent worktree at all.

**The rule.** A session running from a child worktree:

- **MAY** read parent state via `git -C <parent> log/status/show/diff`.
- **MAY NOT** edit files in the parent worktree.
- **MAY NOT** commit, push, or `cd` into the parent worktree.

`mill-merge` and `mill-cleanup` are the only legitimate parent-write skills; they operate via `git -C <parent>`, never `cd`.

**Where to encode it.**

1. Add a "Worktree isolation" section to `plugins/mill/skills/conversation/SKILL.md`. The conversation skill is loaded on every startup.
2. Audit `plugins/mill/skills/` for stray `cd <parent>` patterns and parent-side `git add / commit / push` calls outside `mill-merge` and `mill-cleanup`. Fix anything found.

This happens during Part A.3's skill-flipping — while the skill text is already being edited for Python entrypoints, the worktree-isolation rule is added in the same pass. One audit, one fix.

**Acceptance:**
- `conversation/SKILL.md` has a "Worktree isolation" section.
- `grep -rE 'cd.*parent|cd.*\.\..*main' plugins/mill/skills/` returns no matches outside `mill-merge` and `mill-cleanup`.

### C.2 — Skill-text `UNKNOWN` verdict fallback

Today's `mill-go` and `mill-start` skill texts handle `APPROVE` and `REQUEST_CHANGES` but not `UNKNOWN`. When B.2's bug fired, the skill was left guessing; workaround was to read the review file directly every time.

B.2 above should make `UNKNOWN` rare. But the skill text still needs a defensive fallback. Add: "If verdict is `UNKNOWN`: read the review file at the returned path and parse the verdict from its frontmatter `verdict:` field. If that fails, halt and surface to the user." Applies to `mill-go` (code review), `mill-start` (discussion review), and (once it exists in W3) `mill-plan` (plan review).

**Acceptance:** a simulated `UNKNOWN` return (by mocking the verdict parser's output) causes the skill to read the review file and continue correctly, instead of halting with confusion.

---

## Part D — Heavy testing

This is not optional. The user's pain point is explicit: "review-spawner som ikke returnerer, og slikt tull". Script migration without testing ships the same class of bugs in a new language. W1 merges only when all of D.1-D.6 are green.

### D.1 — Subprocess contract verification per entrypoint

Every new Python entrypoint from Part A gets an integration test that exercises the subprocess contract explicitly. The contract is:

1. **Exit code.** The entrypoint exits with `0` on success, non-zero on failure. No exit code means "hung".
2. **Timeout.** Every subprocess spawn has an explicit timeout. If the child has not returned within the timeout, the parent kills it and exits non-zero with a clear "subprocess timeout" error.
3. **stdout/stderr propagation.** The entrypoint's stdout is the child's stdout (or a clearly-labelled wrapper). The entrypoint's stderr includes the child's stderr, prefixed to disambiguate.
4. **Blocking semantics.** The parent process blocks until the child returns. No fire-and-forget. No "returned success before the work finished". This is the bug class the user called out explicitly.
5. **Encoding.** All subprocess calls specify `encoding='utf-8'` and `errors='replace'` on Windows. No implicit cp1252 fallbacks.
6. **No shell injection.** Every subprocess call passes arguments as a list, never as a joined string with `shell=True`.

**Per-entrypoint test file.** For each entrypoint `millpy/entrypoints/<name>.py`, create `tests/entrypoints/test_<name>.py` with:

- Happy path: invoke with valid args, assert exit code 0 and expected stdout shape.
- Missing required arg: assert exit code non-zero, stderr mentions the missing arg.
- Timeout: invoke with a deliberately-slow mock child, assert timeout fires and exit code is non-zero.
- Subprocess failure: invoke with a mock child that exits non-zero, assert the parent's exit code reflects it.
- Encoding edge case: invoke with non-ASCII input, assert output round-trips correctly.

### D.2 — Cross-layout tests

Every entrypoint is tested in **two** layouts:

1. **Flat layout** — git root equals project root. `c:/Code/millhouse` style. The common case.
2. **Nested-project layout** — git root does not equal project root. A fixture repo at `tests/fixtures/nested-project/` has the `_millhouse/` directory at `projects/sub/_millhouse/` while the git root is two levels up.

Running the same entrypoint against both layouts must produce equivalent results. This catches the class of "spawn_reviewer uses git root for `_millhouse/` path" bugs that bit the external project case (covered structurally by B.1).

**The test matrix covers both new entrypoints AND pre-existing ones.** `spawn_reviewer.py` is pre-existing; its cross-layout test is how B.1's fix is verified.

### D.3 — End-to-end smoke against a dummy task

Write a small fixture task under `tests/fixtures/dummy-task/` that exercises the full skill chain:

1. Fresh `mill-setup` in an empty temp directory.
2. `mill-spawn` to claim the dummy task and create a worktree.
3. `mill-start` → Phase: Discussion (scripted input for interactive parts).
4. `mill-plan` equivalent (today's `mill-go` P2) → Phase: Plan + Plan Review (happy path; mocked reviewer responses).
5. `mill-go` → Phase: Run (happy path; mocked implementer spawns).
6. `mill-merge` → Phase: Merge.

The test runs the full chain in a temp git repo, verifies each phase transition, and verifies that **no PS1 process is spawned at any point** — the test harness watches for any `*.ps1` in the process table and fails if one appears. This is both a regression test and a living document of "what it looks like when mill works end to end".

### D.4 — Parity tests against the old PS1 scripts

For each PS1 script being deleted in A.4, keep the PS1 file in place during W1 implementation and write a parity test that runs **both** the PS1 script and the new Python entrypoint with the same inputs, then diffs their outputs. Tolerances are explicit (timestamps normalized, absolute paths rewritten to relative). Any diff that cannot be explained by intentional behavior changes is a bug.

Parity tests are deleted along with the PS1 files in A.4 after they pass once. They do not ship as permanent tests — the entrypoint-level tests in D.1 are the ongoing regression safety net.

### D.5 — No flake tolerance

The full test suite (D.1 + D.2 + D.3 + D.4) must pass **three consecutive runs** before W1 is merged. A single intermittent failure is a blocker. Subprocess tests are the most common source of flake, and one of the bug classes the user called out is "script doesn't return" — which is exactly what manifests as occasional flake before becoming a hard failure.

### D.6 — Observability

Every entrypoint's subprocess spawns emit structured log lines to stderr:

```
[millpy.<entrypoint>] spawning: <command> <args>  (timeout=<N>s, pid=<parent-pid>)
[millpy.<entrypoint>] child exited: pid=<child-pid> exit-code=<N> duration=<N>s
```

This makes "the script hung" diagnosable after the fact without re-running. The log format is consistent across all entrypoints so grep / filter tooling works uniformly.

---

## Moved to W3 (not in this worktree)

**`[autonomous-fix]` commit prefix policy for spawned subprocesses.** Originally planned here as Fix 8. Moved to W3 because W3 rewrites the entire orchestrator brief (Thread B becomes Opus, Thread A owns WHAT, Thread B owns HOW, receiving-review loop lives in Thread B, etc.). Patching today's Sonnet-orchestrator brief in W1 only to delete-and-rewrite it in W3 is wasted work. The policy lands in W3 as a new Part E of that proposal.

---

## Non-goals

- **Porting `notify.sh` to Python.** Bash leaf utility, not PS1, and not referenced from any skill text.
- **Rewriting the reviewer engine.** Already Python. Touched only via the shared verdict helper in B.2.
- **Changing the plan format.** W2.
- **Changing the mill-go executor.** W3.
- **Automated cache-junction repair.** A.2 step 5 reports dangling junctions but does not repair them. Automated repair is a nice-to-have for a later worktree.
- **Full consolidation of the three plugin-lookup mechanisms.** The external bug report (#9) flagged that plugin files are reached three different ways (marketplace source, plugin cache, caller-relative). Consolidation is a separate post-v3 cleanup; W1 fixes only `spawn-agent` (by porting to Python where it is naturally resolved through the cache).

## Dependencies

- None. W1 is the foundation. W2 and W3 both assume its Python-only skill surface.

## Risks and mitigations

- **Porting `spawn-agent.ps1` introduces a regression.** The PS1 script has been running for months; subtle behaviors (encoding, line endings, stdout buffering) may differ in the Python port. Mitigation: D.4's parity tests catch diff-able differences; D.3's end-to-end smoke catches behavioral differences.
- **`mill-setup` Python port breaks fresh-clone setup for real users.** The migration touches user-visible first-run behavior. Mitigation: test A.2 against a pristine temp directory with no `_millhouse/` present; ship only after the D.3 smoke passes three consecutive runs.
- **`resolve_reviewer_name` legacy fallback is the only thing letting old user configs keep working after the rename.** If the fallback path regresses, users with pre-rename configs will hit `unknown reviewer` errors. Mitigation: explicit unit test for the legacy-name fallback path, plus a one-liner note in the commit message telling users to re-run `mill-setup` at their convenience.
- **W1 is large.** Nine original fixes + the Python migration + heavy testing. It is the biggest worktree in the backlog. Mitigation: batch commits at each Part boundary (A.1 spawn_agent, A.2 setup, A.3 skill-flip, A.4 deletes, B.1 path resolver, B.2 verdict helper, B.3 list-reviewers, C.1 isolation rule, C.2 UNKNOWN fallback, D.1-D.6 test suite). Each batch is its own commit and its own resume point.
- **Cross-layout testing surfaces additional pre-existing bugs beyond B.1.** D.2 might find that other entrypoints also have the git-root-assumption bug. Mitigation: accept the finding as in-scope — fix whatever D.2 surfaces rather than carving it into a follow-up. W1 is where path-resolution gets straightened out once.
- **Subprocess contract edge cases are hard to test.** Mitigation: D.1's test matrix covers the known edge cases; D.6's observability makes new edge cases diagnosable after the fact.

## Acceptance criteria (the full gate before merge)

1. **A.1:** `millpy/entrypoints/spawn_agent.py` exists and passes D.1 tests. `spawn-agent.ps1` deleted.
2. **A.2:** `millpy/entrypoints/setup.py` exists and passes D.1 + D.3 tests. `mill-setup/SKILL.md` calls it. Fresh `mill-setup` in an empty temp directory produces a correct `_millhouse/config.yaml` (short reviewer names, no dead `reviewers:` block, no duplicate `models:` slots).
3. **A.3:** `grep -rE '\.ps1' plugins/mill/skills/` returns zero matches.
4. **A.4:** All listed PS1 files deleted. No skill references them.
5. **B.1:** cross-layout test from D.2 passes for `spawn_reviewer.py` in both flat and nested-project layouts.
6. **B.2:** three unit tests cover `` `X` ``, ``` ```X``` ```, ``` ```json\nX\n``` ``` verdict-line wrappings. End-to-end runs parse wrapped verdicts correctly.
7. **B.3:** `spawn_reviewer.py --list-reviewers` prints both registries. `unknown reviewer` error mentions the flag.
8. **C.1:** `conversation/SKILL.md` has a "Worktree isolation" section. Grep finds zero stray `cd <parent>` patterns in skill text.
9. **C.2:** simulated `UNKNOWN` verdict return causes the skill to read the review file and continue correctly.
10. **D.1:** every entrypoint has a test file under `tests/entrypoints/` covering the full contract matrix. All green.
11. **D.2:** every entrypoint passes in both flat and nested-project layouts. All green.
12. **D.3:** end-to-end smoke passes against the dummy task fixture. No PS1 process spawned anywhere in the chain.
13. **D.4:** parity tests for every ported PS1 script passed at least once before the PS1 was deleted. (Parity tests themselves are then deleted.)
14. **D.5:** the full suite (D.1 + D.2 + D.3) passes three consecutive runs with no flake.
15. **D.6:** every entrypoint emits structured spawn / exit log lines.

Only when 1-15 are all green does W1 merge. If any are red, fix the underlying bug and re-run. **Do not tighten the gate and move on.**
