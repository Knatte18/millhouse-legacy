# Tasks


`tasks.md` lives on main today, so every task reshuffle pollutes main's history. Move it to an orphan branch `tasks` that never merges into main. Git-synced across machines, viewable on GitHub via `github.com/Knatte18/millhouse/blob/tasks/tasks.md`, editable locally via a dedicated worktree.

- Self-reinforcement: The two orchestrators (and potentailly also some of the other subthreads): IF a clear bug is detected by the thread, it can ITSELF invoke the "millhouse-issue" skill and report the bug. 
Perhaps wait to do this until the thread's task is fully done. Then an accumulated reports can be destilled to create an accurate bug-issue for the millhous eto be set. 
I can then manually pull down the issues, have Opus analyse them as an ensamble, and fix in one-go.

- Do not hardcode templates in a skill: INGEN av skillene som oppretter filer skal ha hardkodet template. Jeg ser at f.eks step *Step 4c i mill-setup har en hardkodet "config". Vi har laget "millhouse-config.yaml" som en template som skal bruke i stedet. INGEN slik hardkodet template skal inn i noen skill. Det skal brukes en template-fil i stedet. Dette gjør det mye enklere å ender templaten. Sjekk også om det er noen andre skill som gjør dette. 


## Self-reinforcement loop: auto-reporting + auto-revise-tasks + simpler task picking

Close the full loop between orchestrators, GitHub issues, and `tasks.md`. Three related pieces, one task:

**1. Self-reinforcement — orchestrators auto-report bugs**

The two orchestrators (and potentially other subthreads): IF a clear bug is detected by the thread, it can ITSELF invoke the `millhouse-issue` skill to report it. Wait until the thread's task is fully done, then distill accumulated observations into an accurate bug-issue.

Design questions:

- When does the thread fire (after `complete`? after review? after merge?)
- Where does it accumulate observations during the run (scratch file?)
- Dedup against existing open issues before filing
- Which threads/skills are allowed to report (just mill-go / Thread B? reviewers too?)
- Togglable via a config entry (on/off)

**2. Revise-tasks skill — automated inbox-driven task consolidation**

A new skill (e.g. `mill:revise-tasks` or extend `mill-inbox`) that performs the full revision flow, not just 1:1 import:

1. Fetch issues via `fetch-issues.py`.
2. For each issue, status-check against the current repo:
   - Already fixed in main → close the issue with a "fixed in main" comment; do not land in tasks.md.
   - Moot (references removed subsystems, obsolete flows) → drop with a written reason; close the issue.
   - Still open → carry forward to the consolidation step.
3. Read the existing `tasks.md` and respect **protected tasks** (marker in config, or a `<!-- protected -->` comment in the task body, or a config-listed set of protected titles).
4. Consolidate: fold issues into existing tasks where they fit; create new tasks where needed; merge related tasks that are not protected.
5. Create **background docs** in `plugins/mill/doc/proposals/` when a new or consolidated task is architecture-level and needs a design grounding.
6. **Present the proposal** to the user before writing (table mapping each issue to its landing place, dropped-with-reason list, new background docs). Wait for green light.
7. On approval: write `tasks.md`, create background docs, commit and push, close GitHub issues with comments pointing to the consolidating task.

This skill is the codification of the manual process used during the 2026-04-17 tasks revision.

**3. Simpler task-selection than `[>]` marker**

The `## [>] <title>` marker that `mill-spawn` reads from `tasks.md` is awkward to type. Preferred approach: make `mill-spawn.py` list all tasks in `tasks.md` numbered (title only), prompt for a number, and claim that one — no manual file editing. Same treatment for `mill-start` if it uses the same marker.

**Why bundled:** (1) fills the issue queue automatically, (2) drains it automatically into tasks via revision, (3) makes picking the next task trivial. Together they are the closed loop; separately they are awkward partial moves.

## Track task state across machines (W4 — needs design)

Invert the `_millhouse/` gitignore so task state (discussion, plan, status, reviews) travels with the branch. Motivated empirically by the millpy task's Step 33, where a gitignored `config.yaml` silently dropped out of an atomic bundle commit. Do not start implementation until the open design questions in the proposal are answered (gitignore granularity, commit cadence, config split, two-machine race handling, `mill-merge` cleanup contract).

**Design doc:** [plugins/mill/doc/proposals/04-track-task-state.md](plugins/mill/doc/proposals/04-track-task-state.md)


## Plan format + review architecture rewrite

- tags: [enhancement, mill-plan, reviewer]
- Consolidates issue #38 (drives), #35 (superseded by #38, folded), #36 (extended by #38, folded), and #34 (folded as threshold gate).
- Introduces a cleaner plan-format contract: `depends-on` = logical deps only; write-safety auto-inferred from `modifies`/`creates`; reviewers stop flagging shared-modifies; `reads` no longer duplicates `modifies` (`Explore ⊆ (Reads ∪ Modifies)`); per-card review gated by a `per-card-threshold` default 20.
- New module `plugins/mill/scripts/millpy/core/plan_dag.py` with `build_enriched_dag(card_index)`.
- Updates: `plan_validator.py` Explore subset rule; `doc/prompts/plan-review.md` holistic prompt; `doc/formats/plan.md` contract section; `mill-go` executor to consume enriched DAG; `mill-plan` SKILL.
- **Background doc:** [plugins/mill/doc/proposals/05-plan-format-contract.md](plugins/mill/doc/proposals/05-plan-format-contract.md)
- No runtime per-file lock layer — single source of truth is the enriched DAG.


## Planner-grouped plan review for large plans

- tags: [enhancement, mill-plan]
- When a plan has 30+ cards, per-card bulk review + holistic tool-use review may not catch inter-group issues effectively. Add an optional Planner-grouped review mode where Planner creates ad-hoc review groups (overlapping subsets of cards) and spawns one reviewer per group in parallel. Same card can appear in multiple groups. Pure Planner-side change — no plan format changes needed.
- Orthogonal to "Plan format + review architecture rewrite" above. Land that first; re-evaluate the grouped approach after.


## Gemini backend: replace CLI with google-genai SDK + tool-use

- tags: [enhancement, reviewer]
- Consolidates issue #31 (drives) and #32 (concrete repro: Gemini CLI hangs on large-prompt bulk dispatch, observed 2026-04-16).
- Replace the Gemini CLI subprocess in `plugins/mill/scripts/millpy/backends/gemini.py` with the `google-genai` SDK.
- Add tool-use support with a `read_file` tool (mirror Ollama's tool-use shape at `plugins/mill/scripts/millpy/backends/ollama.py`).
- Proper API-key auth via env var (`GEMINI_API_KEY` or `GOOGLE_API_KEY`).
- Add timeout + retry logic (Gemini CLI has neither).
- **Interim mitigation already in main:** swap reviewer ensembles from `gemini-3-flash` to `gemini-2.5-flash` (GA).
- Open design questions before implementing:
  - Bulk dispatch: migrate to SDK too, or keep CLI for bulk and only use SDK for tool-use?
  - Python dep: no `pyproject.toml` at repo root currently — how is the `google-genai` dep managed/declared?
  - Auth precedence: env var only, or also `.geminic` config fallback?
  - Model IDs to accept (GA: `gemini-2.5-pro`, `gemini-2.5-flash`; preview: `gemini-3-pro-preview`, `gemini-3-flash-preview`)?


## mill-go Builder-tweaks: session-resume + linear default

- tags: [enhancement, mill-go]
- Two small changes to mill-go's Builder execution. Both touch the same code path and merit one task.

**1. Resume implementer session on REQUEST_CHANGES (#37)**

Today mill-go spawns a fresh Sonnet session on `REQUEST_CHANGES` instead of resuming the session that wrote the original code. The comment "null for current CLI" in [mill-go/SKILL.md:229-236](plugins/mill/skills/mill-go/SKILL.md#L229-L236) is outdated — [spawn_agent.py:89-90](plugins/mill/scripts/millpy/entrypoints/spawn_agent.py#L89-L90) already supports `--session-id` and [spawn_agent.py:207, 224, 258](plugins/mill/scripts/millpy/entrypoints/spawn_agent.py#L207) already emits `session_id`. mill-go just never captures or reuses it.

Fix:

1. After the first implementer spawn for a card, parse `session_id` from the spawn's JSON output. Persist it per card (e.g. `status.md` entry `card_<N>_session_id: <id>`).
2. On `REQUEST_CHANGES`, resolve the card's `session_id` and spawn with `spawn_agent.py --session-id <id>`.
3. Fallback to a fresh Sonnet session only if `session_id` is missing or `claude --resume` fails.
4. Update [mill-go/SKILL.md:229-236](plugins/mill/skills/mill-go/SKILL.md#L229-L236) to describe resume as primary, fresh as fallback.

Benefits: context bevaring (implementer knows why it made each choice), token savings (prompt-cache hits within 5 minutes give ~90% discount), faster iteration.

Open questions:

- Session lifetime — how long before a session is too stale to resume?
- Session death handling — fall back to fresh and log.
- Per-card vs. per-run session — stay per-card (current implicit model)?

**2. Linear execution as default; DAG-parallel as opt-in**

Observed 2026-04-17: running Builder linearly on a multi-card plan was fast enough and simpler to follow than parallel DAG execution. Parallel-DAG code path has bugs and extra complexity that do not earn their keep for the plan sizes we run today.

Fix:

1. Add `pipeline.executor.parallel` to `_millhouse/config.yaml` (default `false`). Or a CLI flag (`--parallel`).
2. mill-go default execution mode: linear, single-threaded — cards in DAG order, one at a time.
3. Keep all DAG-parallel infrastructure intact — it stays behind the flag for future reactivation.
4. Document the default in `mill-go/SKILL.md`.

No removal of DAG code. The `plan_dag.py` work from the Plan-format task stays useful for linear ordering — just without the concurrency.


## mill-spawn / mill-vscode / mill-terminal: subfolder + nested-repo fixes

- tags: [bug]
- Two related bugs in the CLI wrappers and `spawn_task.py` when invoked from subdirectories or nested mill-projects.

**1. Path-mirroring: preserve cwd subfolder when switching worktrees**

`mill-vscode.py` and `mill-terminal.py` should open in the subfolder of the new worktree that matches the subfolder of the parent worktree they were invoked from.

- Parent worktree: `C:/Code/millhouse`
- Invoked from: `C:/Code/millhouse/plugins/mill/scripts/`
- New worktree: `C:/Code/millhouse.worktrees/<slug>/`
- Expected behavior: open at `C:/Code/millhouse.worktrees/<slug>/plugins/mill/scripts/`
- Current behavior: opens at the worktree root

Fix: compute the path offset from cwd to the parent's `project_root()` / `repo_root()`, then append that offset to the new worktree's root.

**2. Worktree location for nested mill-projects uses `project_root()` instead of `repo_root()`**

[spawn_task.py:168](plugins/mill/scripts/millpy/entrypoints/spawn_task.py#L168):

```python
worktrees_dir = root.parent / f"{root.name}.worktrees"
```

Here `root` comes from `project_root()`, which walks up from cwd to the nearest `_millhouse/` directory. For nested mill-projects inside a git repo, this gives the wrong answer.

- Git repo root: `C:/Code/py`
- Mill project root (cwd): `C:/Code/py/projects/piprocessing` (has its own `_millhouse/`)
- Current behavior: `worktrees_dir = C:/Code/py/projects/piprocessing.worktrees` (inside the git repo — wrong)
- Expected behavior: `worktrees_dir = C:/Code/py.worktrees` (sibling of the git repo — correct; `git worktree add` only operates at the git-repo level)

Fix: use `repo_root()` (git toplevel) for the worktree container calculation. Keep `project_root()` for `_millhouse/` and `tasks.md` resolution. When the user opens the new worktree, they navigate to the matching subfolder — same as fix 1 above.
