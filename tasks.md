# Tasks


## Self-reinforcement by automated bug-reporting and no hardcoded templates in skill files

- Self-reinforcement: The two orchestrators (and potentailly also some of the other subthreads): IF a clear bug is detected by the thread, it can ITSELF invoke the "millhouse-issue" skill and report the bug. 
Perhaps wait to do this until the thread's task is fully done. Then an accumulated reports can be destilled to create an accurate bug-issue for the millhous eto be set. 
I can then manually pull down the issues, have Opus analyse them as an ensamble, and fix in one-go.

- Do not hardcode templates in a skill: INGEN av skillene som oppretter filer skal ha hardkodet template. Jeg ser at f.eks step *Step 4c i mill-setup har en hardkodet "config". Vi har laget "millhouse-config.yaml" som en template som skal bruke i stedet. INGEN slik hardkodet template skal inn i noen skill. Det skal brukes en template-fil i stedet. Dette gjør det mye enklere å ender templaten. Sjekk også om det er noen andre skill som gjør dette. 


## Self-reinforcement loop: auto-reporting + auto-inboxing + simpler task picking

Close the full loop between orchestrators, GitHub issues, and `tasks.md`. Three related pieces, one task:

**1. Self-reinforcement — orchestrators auto-report bugs**

The two orchestrators (and potentially other subthreads): IF a clear bug is detected by the thread, it can ITSELF invoke the `millhouse-issue` skill to report it. Wait until the thread's task is fully done, then distill accumulated observations into an accurate bug-issue.

Design questions:
- When does the thread fire (after `complete`? after review? after merge?)
- Where does it accumulate observations during the run (scratch file?)
- Dedup against existing open issues before filing
- Which threads/skills are allowed to report (just mill-go / Thread B? reviewers too?)
- The self-reinforcement should be togable: an entry in config giving on/off

**2. Automated inbox processing — distill issues back into tasks**

Extend `mill-inbox` (or add a sibling skill) that:
1. Fetches issues from GitHub (reuses `fetch_issues.py`).
2. For each issue, status-checks the current repo: already fixed? architecturally mitigated? moot? still open? (Same analysis Claude did manually during inbox 2026-04-16.)
3. Groups many small bugs into one or a few consolidating tasks in `tasks.md` — NOT a 1:1 import. Open/partial items go into an active task; moot items get noted and closed.
4. Closes the GH issues with a comment pointing to the consolidating task.

**3. Simpler task-selection than `[>]` marker**

The `## [>] <title>` marker that `mill-spawn` reads from `tasks.md` (see `mill-spawn/SKILL.md:81`) is awkward to type. Preferred approach: make `mill-spawn.py` list all tasks in `tasks.md` numbered (title only), prompt for a number, and claim that one — no manual file editing. Same treatment for `mill-start` if it uses the same marker.

**Why bundled:** (1) fills the issue queue automatically, (2) drains it automatically into tasks, (3) makes picking the next task trivial. Together they're the closed loop; separately they're awkward partial moves.



## Planner-grouped plan review for large plans
- When a plan has 30+ cards, per-card bulk review + holistic tool-use review may not catch inter-group issues effectively. Add an optional Planner-grouped review mode where Planner creates ad-hoc review groups (overlapping subsets of cards) and spawns one reviewer per group in parallel. Same card can appear in multiple groups. Pure Planner-side change — no plan format changes needed.


## Track task state across machines (W4 — needs design)

Invert the `_millhouse/` gitignore so task state (discussion, plan, status, reviews) travels with the branch. Motivated empirically by the millpy task's Step 33, where a gitignored `config.yaml` silently dropped out of an atomic bundle commit. Do not start implementation until the open design questions in the proposal are answered (gitignore granularity, commit cadence, config split, two-machine race handling, `mill-merge` cleanup contract).

**Design doc:** [plugins/mill/doc/proposals/04-track-task-state.md](plugins/mill/doc/proposals/04-track-task-state.md)



## [done] General bugfix sweep — inbox 2026-04-16

- tags: [bug]
- See `_millhouse/task/discussion.md` for the full evolved scope. Scope summary:
- **mill-vscode.py color** — spawned VS Code instance gets same titleBar color as parent (user-reported 2026-04-16). Fix `_pick_worktree_color()` so child worktrees exclude main's green; mill-setup enforces green for main worktree; add a small `mill-color.py` script for ad-hoc color override.
- **spawn_reviewer ERROR vs UNKNOWN (#24a)** — verify via regression test that worker non-zero exit returns `ERROR`, not `UNKNOWN`.
- **Reviewer filename slice-id (#24b)** — audit callers + update `mill-start/SKILL.md` docs that reference obsolete filename format.
- **PR-land lifecycle (#25)** — document in `mill-merge/SKILL.md` that git merge carries `[done]` from child to parent naturally. No code change.
- **mill-go path-anchoring (#23)** — replace `(cd plugins/mill/scripts && python -m X)` with `PYTHONPATH`-based invocation; introduce `<SCRIPTS_DIR>` token. Sweep all callers.
- **mill-start child-worktree guard (#22)** — remove the guard entirely.
- **NavigationHooks cleanup** — delete all 7 references (codeguide-setup/SKILL.md + resolve.py docstring).
- **Helm sweep (#17, #18)** — verified clean; close both as moot.
- **Templates audit** — migrate 5 multi-line inline templates to `plugins/mill/templates/`. Refresh existing `templates/millhouse-config.yaml` to current pipeline schema.
- **Empty-shell discussion.md placeholder** — remove `_write_discussion_placeholder()` from `spawn_task.py`.
- **Background spawns** — update `mill-start`, `mill-plan`, `mill-go`, and `implementer-brief.md` so long-running spawns (reviewers, implementers) use `run_in_background: true` + `Monitor` so user and assistant can keep conversing while the spawn runs.
- **plan_validator Explore-path parsing** — `_extract_bullet_paths()` treats every backtick-wrapped token in Explore bullets as a path, producing false BLOCKING errors on code identifiers in commentary. Restrict path detection to tokens containing `/` or ending in a known source-file extension.

Moved out of this sweep:
- Gemini CLI → google-genai SDK migration (#31) — see separate task below.



## Auto-infer write-safety deps in plan DAG

- tags: [enhancement, mill-plan, mill-go]
- Currently Planner must manually declare `depends-on` between cards that modify the same file — otherwise parallel execution of cards in the same DAG layer produces merge conflicts. Observed 2026-04-16: 4 rounds of holistic review caught this pattern repeatedly (cards 3/9, 6/10, 7/11, 3/12 etc. all needed manual ordering deps just because they shared a file).
- **Smart fix — two layers:**
  1. **Plan-time auto-inference:** `plan_validator` (or a new `plan_dag` module) scans all cards, builds `file → [card_numbers]` map from each card's `modifies` + `creates`, and for any file with 2+ cards injects implicit ordering edges (lower card-number first, deterministic). These auto-deps supplement Planner's explicit `depends-on`. Planner declares only **logical** deps (output of card A is input to card B). Write-safety is automatic.
  2. **Runtime serialization (safety net):** `mill-go` DAG-executor takes per-file locks during implementation. Cards in the same layer that write the same file are serialized; disjoint-file cards still run in parallel. Extra insurance even if plan-time inference misses something.
- **Benefits:**
  - Planner writes ~40% fewer deps (just logical ones)
  - No "cards A and B both modify F without dep" reviewer findings
  - Cleaner division of concerns: Planner does intent, validator does safety
- **Implementation sketch:** `plan_dag.py` new module; `validate()` returns both the explicit DAG and the enriched DAG (with auto-deps); mill-go uses the enriched DAG for execution. Overview `depends-on` fields stay as Planner wrote them (logical only); enriched DAG is computed view.



## Drop per-card plan review; holistic already covers it

- tags: [enhancement, reviewer, mill-plan]
- Current mill-plan Phase: Plan Review fans out N per-card reviewers + 1 holistic. Per observation 2026-04-16: the holistic prompt is overloaded — it already covers atomicity, requirements testability, reads-completeness, step granularity, explore⊆reads. The per-card reviewers duplicate that work with higher token cost and marginal added value.
- **Change:** drop per-card fan-out. Run holistic only. Shrink cost per plan review by ~13x for a 13-card plan.
- **Rebalance holistic prompt** at `plugins/mill/doc/prompts/plan-review.md` to sharpen its focus:
  - Keep: constraint violations, design-decision alignment, cross-card conflicts (same-file-without-dep), DAG correctness, overall completeness against task scope, batch graph integrity
  - Drop (already per-card): atomicity invariant, requirements testability, explore⊆reads, reads-completeness detail (holistic sees but doesn't need to deep-check)
- **Keep per-card as opt-in** for very large plans (threshold ~20+ cards) where holistic may skim. Threshold configurable via `pipeline.plan-review.per-card-threshold` in config.
- **Skill edits:** mill-plan/SKILL.md Phase: Plan Review — remove per-card fan-out by default, add threshold check.
- **Motivation:** observed during 2026-04-16 plan-review run (13 cards, 14 parallel sonnet spawns for R1 = ~$1.50). Holistic sonnetmax alone caught all BLOCKING issues per-card reviewers flagged, plus DAG conflicts per-card reviewers couldn't see.



## Gemini backend: replace CLI with google-genai SDK + tool-use (#31)

- tags: [enhancement, reviewer]
- Replace the Gemini CLI subprocess in `plugins/mill/scripts/millpy/backends/gemini.py` with the `google-genai` SDK.
- Add tool-use support with a `read_file` tool (mirror Ollama's tool-use shape at `plugins/mill/scripts/millpy/backends/ollama.py`).
- Proper API-key auth via env var (`GEMINI_API_KEY` or `GOOGLE_API_KEY`).
- Add timeout + retry logic (Gemini CLI has neither).
- **Motivation:** Gemini CLI is unstable — parked out of the `general-bugfix-sweep` on 2026-04-16 because scope required more design thinking. Interim mitigation (swap reviewer ensembles from gemini-3-flash to gemini-2.5-flash, which is GA) is already in main as of 2026-04-16.
- Open design questions before implementing:
  - Bulk dispatch: migrate to SDK too, or keep CLI for bulk and only use SDK for tool-use?
  - Python dep: no `pyproject.toml` at repo root currently — how is the `google-genai` dep managed/declared?
  - Auth precedence: env var only, or also `.geminic` config fallback?
  - What model IDs to accept (GA: `gemini-2.5-pro`, `gemini-2.5-flash`; preview: `gemini-3-pro-preview`, `gemini-3-flash-preview`)?

