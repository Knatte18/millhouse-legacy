# Proposal 02 — Plan-Format v2: Batch-Plan Directories, Planner, Reviewer

**Status:** Proposed
**Worktree:** W2 — ships as one v1 plan (chicken-egg: the v2 format does not exist yet)
**Depends on:** W1 (for real-world adoption, not technically)
**Blocks:** W3 (mill-go v2 executor requires the v2 format and planner output)

## One-line summary

Replace the single-file `_millhouse/task/plan.md` with a `_millhouse/task/plan/` directory containing an overview file and per-batch files, add per-card dependency metadata (`depends-on:` / `touches-files:`) so a downstream executor can build a DAG, teach `mill-plan` to write the new format, rewrite plan review to run per-batch with an ensemble, and add a language-specific-pitfalls criterion to the review prompt.

## Background

The millpy task ran a 1461-line single-file plan through three plan-review rounds, hit `max_turns=20` during round 2 (Sonnet reviewer couldn't read the plan plus referenced source files in one budget), missed a basic Python stdlib collision (`core/logging.py`) across three reviewers, and sprawled across 38 cards that the orchestrator had to batch externally at execution time. All four problems have the same root cause: the plan format has no structural unit between "the whole plan" and "one step card", and no way to declare cross-card dependencies.

This proposal is the most impactful structural change in the backlog. It unlocks:

- **Reviewer budget relief** — each batch file is 200-400 lines instead of 1500+, so reviewers no longer exhaust their turn budget.
- **Natural parallelism** — per-card `depends-on:` metadata lets the executor build a DAG, topologically sort into layers, and spawn one worker per card within a layer.
- **Progressive review** — independent batches can be reviewed in parallel; approved batches can start implementing before later batches are drafted.
- **Cleaner audit and bisect** — one batch per architectural concern, global card numbering preserved, one commit per card.
- **Lower cognitive load** — humans browse a directory, not scroll a 1500-line file.

## Part A — Plan-format v2 spec

Update `plugins/mill/doc/formats/plan.md` (or wherever the format reference currently lives) to describe the v2 layout. No skill or orchestrator code in Part A — this is documentation only, so the next parts have an authoritative reference.

### Directory layout

```
_millhouse/task/
├── plan/
│   ├── 00-overview.md
│   ├── 01-core.md
│   ├── 02-tasks-worktree.md
│   ├── 03-backends.md
│   ├── 04-reviewers.md
│   ├── 05-doc-reorg.md
│   └── 06-finalization.md
├── discussion.md
└── status.md
```

Filename convention `NN-<slug>.md`: two-digit prefix for filesystem sort, hyphenated slug for the batch name. mill-plan / mill-go parse the `batch-name` from frontmatter, not from filename — renames are safe.

### `00-overview.md` — the shared backbone

```markdown
---
kind: plan-overview
task: <task title>
verify: <build/test command>
dev-server: <dev server command or N/A>
approved: false
started: <UTC timestamp>
batches:
  - 01-core
  - 02-tasks-worktree
  - 03-backends
  - 04-reviewers
  - 05-doc-reorg
  - 06-finalization
---

# <Task Title>

## Context
(Problem statement, approach framing, high-level what-and-why. 200-400 words.)

## Shared Constraints
(Invariants that apply to every batch unless explicitly overridden. One-line rule
 per bullet + brief rationale. Examples: "Stdlib-only, no third-party imports",
 "UTF-8, no BOM, LF line endings on all file writes", "All subprocess calls
 through core/subprocess_util.run", "log_util.py NOT logging.py — stdlib collision".)

## Shared Decisions
(Decisions that affect more than one batch. One `### Decision: <title>` subsection
 each, with **Why** and **Alternatives rejected**. Single authoritative location —
 batch files reference these instead of duplicating them.)

### Decision: <title>
### Decision: <title>

## Batch Graph

```yaml
batches:
  01-core:
    depends-on: []
    summary: "Skeleton + core utilities."
  02-tasks-worktree:
    depends-on: [01-core]
    summary: "tasks/ and worktree/."
  03-backends:
    depends-on: [01-core]
    summary: "Backend Protocol + implementations + registry."
  04-reviewers:
    depends-on: [01-core, 02-tasks-worktree, 03-backends]
    summary: "Reviewer base types + ensemble dispatch + engine + entrypoint."
  05-doc-reorg:
    depends-on: []
    summary: "Doc directory split."
  06-finalization:
    depends-on: [04-reviewers, 05-doc-reorg]
    summary: "Atomic switchover + smoke tests + final verification."
```

## All Files Touched (across all batches)
(Flat list of every file any batch creates, modifies, or deletes. Used by
 mill-go's staleness check and by plan-review's cross-batch integration check.)
```

The overview file is never implemented. It has no step cards. It is read by every reviewer and every implementer, but it never drives a commit directly.

### `NN-<slug>.md` — one batch file per batch

```markdown
---
kind: plan-batch
batch-name: core
batch-depends: []
approved: false
---

# Batch 01: core utilities

## Batch-Specific Context
(Only decisions specific to THIS batch. Most batches have zero batch-specific
 decisions — they inherit everything from overview. Example of a valid
 batch-specific decision: "extract _parse_claude_json_wrapper as a pure helper",
 which only matters for the backends batch.)

## Batch Files
(Only files this batch touches — a strict subset of the overview's "All Files Touched".)

- plugins/mill/scripts/millpy/core/subprocess_util.py
- plugins/mill/scripts/millpy/core/log_util.py

## Steps

### Step 1: Create millpy package skeleton and _bootstrap.py

- **Creates:** plugins/mill/scripts/millpy/__init__.py, plugins/mill/scripts/millpy/_bootstrap.py
- **Depends on:** []
- **Touches files:** [millpy/__init__.py, millpy/_bootstrap.py]
- **Requirements:**
  - Package must import cleanly as `import millpy`.
  - `_bootstrap.py` exposes `REPO_ROOT` and `PROJECT_ROOT`.
- **Commit:** `millpy: create package skeleton`

### Step 2: Create core/subprocess_util.py
- **Depends on:** [Step 1]
- **Touches files:** [millpy/core/subprocess_util.py, tests/core/test_subprocess_util.py]
...
```

Batch files are the unit of implementation. A fresh implementer subagent receives `00-overview.md` + one batch file as input and implements all cards in that batch sequentially.

### Card-level frontmatter additions

Every `### Step N:` card grows two new fields:

- **`depends-on:`** — list of step numbers. Declares "this card cannot execute until those cards have produced their artifacts". Written by the planner (WHAT-level thinking — the planner knows, e.g., that Step 14 imports from Step 13). Read by the executor to build the DAG.
- **`touches-files:`** — list of repo-relative paths. The union of `Creates:` and `Modifies:` for the card. Used by the executor to detect file-level conflicts between cards in the same layer (two cards touching the same file must serialize even if their declared `depends-on` does not require it).

Card numbering is **global across batches**. Batch 01 contains cards 1-7, batch 02 contains 8-12, etc. This preserves the "per-card commit" invariant — each card's commit message and git-log entry stays globally unique. Card numbering is FILENAME-ordered, not dependency-ordered; cards within a batch are still executed sequentially within that batch's subagent (layer-parallel execution comes in W3).

### Backwards compatibility

- If `_millhouse/task/plan/` (directory) exists: use v2.
- Else if `_millhouse/task/plan.md` (file) exists: use v1.
- If both exist: the directory wins and a warning is logged.
- No automated migration. Old in-flight tasks run to completion on v1; new tasks use v2.

### Open questions deferred to W3

- **Cross-batch shared helper visibility.** Batch 01 defines `_parse_yaml_mapping`, batches 02 and 04 use it. The dependency is real. W2's answer: batch 02's `batch-depends: [01-core]` makes the use legal, but nothing in batch 02's file list names the helper. Reviewer has to cross-check. A future v3 could add `imports-from-batch: [01-core: _parse_yaml_mapping]` for tighter validation. Out of scope for W2.
- **Card fusion.** Some "file-only" cards could be fused with adjacent cards without losing atomicity. W2 documents the constraint but doesn't automate fusion detection.

### Part A acceptance

- `plugins/mill/doc/formats/plan.md` (or the current format reference location) describes the v2 layout with working examples for both `00-overview.md` and a representative batch file.
- A fresh Opus session can write a valid v2 plan using only the format reference, without needing to read this proposal.
- The plan-format validator accepts both v1 (`plan.md` file) and v2 (`plan/` directory) and flags malformed frontmatter in either.

---

## Part B — `mill-plan` writes v2 directories

Teach the current plan-writing skill to produce v2 directories. For W2, `mill-plan` is still the plan-writing portion of today's `mill-go` — the skill-level split to a standalone `mill-plan` skill is W3's job.

### Writing flow

1. **Draft `00-overview.md` first.** Context, Shared Constraints, Shared Decisions, Batch Graph (initially with stub one-line summaries), All Files Touched (initially empty). This anchors the architecture.
2. **Write each batch file sequentially.** For each batch in the graph: draft context, list batch files, write step cards with full frontmatter including `depends-on:` and `touches-files:`. As batches accumulate, update `All Files Touched` in the overview.
3. **Parallel batch writing is allowed but not required.** Batches with no design dependencies (e.g., `01-core` and `05-doc-reorg`) can be drafted by parallel Opus sessions if the planner wants the speedup. Sequential is simpler and the first cut.

### Dogfood

`mill-plan` writes its own task's plan in v2 format as a smoke test of the planner → format round trip. The format's first real user is the skill that produces it.

### Part B acceptance

- Running the updated `mill-plan` on a fresh task produces a valid v2 directory under `_millhouse/task/plan/`.
- The plan-format validator accepts the output.
- The W2 task itself ships with a v2 plan (recursive dogfood).

---

## Part C — Plan-review v2: per-batch + ensemble

Two changes bundled because they share the review-pipeline rewrite.

### C.1 — Per-batch review

Today: one reviewer reads the whole plan, produces one review. Hit `max_turns=20` during millpy.

v2: each batch file is reviewed individually. A reviewer evaluating `04-reviewers` sees `00-overview.md` + `04-reviewers.md` only — not the text of `03-backends`, just the interface promises made in `03-backends`' `batch-depends:` + file list + commit messages.

**Benefits:**
- Reviewer context is bounded (overview + one batch). No more max_turns issues on large plans.
- Reviews for independent batches run in parallel.
- Approval is granular. Approving batch A before batch D is drafted lets implementation of A start immediately (W3 only; W2 ships serial batch review).

**Cross-batch interface review.** What guarantees that batch B correctly uses an interface batch A creates? Answer: the overview file's Shared Decisions + `batch-depends:` form the contract. A reviewer evaluating batch D checks that its cards only use symbols from the batches listed in `batch-depends:`, and that those batches' file lists promise to create the referenced symbols. If a cross-batch reference is made to a symbol not promised by a dependency, the reviewer flags it BLOCKING.

**Integration review.** After all per-batch reviews pass, run one final "integration review" that reads the whole directory and checks cross-batch consistency. This catches what per-batch reviews miss (e.g. the `<FILES_PAYLOAD>` vs `<FILE_BUNDLE>` token mismatch the millpy plan carried to implementation time). Smaller input than a v1 single-file review because it reads summaries and card commit messages, not full card content.

### C.2 — Ensemble plan review

Port the code-review ensemble pattern (Gemini Flash × N + Sonnet handler) to plan review. One Flash call + one Sonnet call + one Opus call in parallel per batch, synthesized by a handler that produces one combined report.

**Motivation.** During the millpy task, Sonnet caught shallow issues, Opus caught deeper contract issues, and neither caught the stdlib collision. Different model capabilities catch different things. The three-worker ensemble pattern mill already uses for code review deserves the same port.

**Reviewer names.** The ensemble entries land in the REVIEWERS registry alongside the code-review ensembles:

- `g3flash-x3-sonnetmax-plan` (plan review equivalent of `g3flash-x3-sonnetmax`)
- A Flash-only variant for faster iteration during draft cycles.

The exact set is picked during implementation based on cost/latency trade-offs.

### C.3 — Language-specific pitfalls criterion

Add a new criterion to `plugins/mill/doc/prompts/plan-review.md`:

```markdown
**Language-specific pitfalls:**

Identify the primary language(s) of the codebase from the plan's paths and existing files.
For each language, check the plan against its common pitfalls:

- **Python:**
  - Module names that shadow stdlib (logging, json, types, os, string, io, etc.)
  - Mutable default arguments (`def f(x=[]):`)
  - Circular imports between sibling modules in the same package
  - `from __future__ import annotations` on dataclasses with frozen=True + Mapping types
  - Subprocess encoding (always set encoding=, errors= on Windows)
  - sys.path manipulation in entrypoints vs conftest.py vs pyproject.toml

- **C#:**
  - Namespace collisions with the BCL
  - `async void` outside event handlers
  - IDisposable forgotten on database/file handles
  - LINQ double-enumeration

- **JavaScript / TypeScript:**
  - `this` binding in arrow vs regular functions
  - Mutation of imported const objects
  - Async error handling without try/catch

Flag any pitfalls the plan would introduce as BLOCKING.
```

One-paragraph addition. Closes a whole class of review blind spots.

### Part C acceptance

- Running the updated plan reviewer against a v2 plan directory produces one review per batch plus one integration review.
- The ensemble variant runs three workers in parallel and synthesizes their output into one combined report.
- A plan that creates `core/logging.py` or any other stdlib-shadowing module is flagged BLOCKING at plan-review time, not at implementation time.

---

## Non-goals

- **Skill-level split to a standalone `mill-plan` skill.** That is W3's responsibility. In W2, the updates to plan-writing and plan-review live in whatever skill currently owns them (today's `mill-go`).
- **Executor changes.** W2 does not touch implementation, DAG building, or Thread B. That is W3.
- **Automated migration from v1 plans.** Old in-flight tasks run to completion on v1; new tasks use v2. No migration tool.
- **Per-card `imports-from-batch:` metadata.** Deferred to a future v3. W2 uses `batch-depends:` + reviewer cross-check.
- **Card fusion detection.** Documented as a known constraint; not automated.

## Dependencies

- No hard dependencies on W1. But W1 unblocks external-project adoption, and W2 is much easier to test on third-party repos if W1 has landed first. Strong preference for W1 → W2 order.
- W3 (mill-go v2 executor) depends on W2 hard — the executor needs the v2 format and the per-card dependency metadata.

## Risks and mitigations

- **Planner drifts back to single-file plans** because v2 is harder to draft. Mitigation: `mill-plan` refuses to write `plan.md` for new tasks; only v2 directories.
- **Reviewer context window explodes** if a batch file is too big. Mitigation: reviewer prompt flags batches outside the 3-8-card sweet spot; planner revises before reviewer runs.
- **Cross-batch references go unreviewed** because per-batch reviewers only see one batch. Mitigation: the integration review round in Part C.1 reads the whole directory after per-batch approval.
- **Ensemble plan review is expensive.** Mitigation: the Flash-heavy ensemble (one Opus + multiple Flash) is cheap enough for draft cycles; full Opus-heavy is reserved for final approval.
