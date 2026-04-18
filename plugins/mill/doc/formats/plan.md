# Plan File Format

## v3 Flat-Card Layout (current format)

For all new tasks, `mill-plan` writes a `.mill/active/<slug>/plan/` directory with a flat-card layout:

```
.mill/active/<slug>/
├── plan/
│   ├── 00-overview.md
│   ├── card-01-add-dag-module.md
│   ├── card-02-update-plan-io.md
│   └── card-03-add-tests.md
├── discussion.md
└── status.md
```

Filename convention `card-NN-<slug>.md`: two-digit prefix for filesystem sort, hyphenated slug. `mill-go` reads the `card-number:` frontmatter field — renames are safe as long as the prefix is updated.

### `00-overview.md` (v3) — shared backbone with Card Index

```markdown
---
kind: plan-overview
task: <task title>
verify: <build/test command, or "N/A">
dev-server: <dev-server command, or "N/A">
approved: false
started: <UTC YYYYMMDD-HHMMSS>
root: <longest common path prefix, or empty string>
---

# <Task Title>

## Card Index

```yaml
1:
  slug: add-dag-module
  creates: [core/dag.py]
  modifies: []
  reads: [core/plan_io.py]
  depends-on: []
2:
  slug: update-plan-io
  creates: []
  modifies: [core/plan_io.py]
  reads: [core/plan_io.py, core/config.py]
  depends-on: [1]
```

## All Files Touched

- core/dag.py
- core/plan_io.py
```

### `00-overview.md` frontmatter fields (v3)

| Field | Required | Description |
|---|---|---|
| `kind` | yes | Must be `plan-overview`. |
| `task` | yes | Task title from `tasks.md`. |
| `verify` | yes | Build/test command used by Builder. |
| `dev-server` | yes | Dev-server command, or the literal `N/A`. |
| `approved` | yes | Starts `false`; Plan Review sets it `true`. Builder refuses to spawn if `false`. |
| `started` | yes | UTC timestamp generated via `date -u +"%Y%m%d-%H%M%S"`. |
| `root` | yes | Longest common path prefix for cards (e.g. `plugins/mill/scripts/millpy`). May be empty string — all paths in the Card Index and card files are then full repo-relative paths. |

### `## Card Index` — DAG metadata (v3)

The Card Index is a fenced YAML block under the `## Card Index` heading. It provides DAG metadata that Builder reads without opening every card file.

**Schema:**
```yaml
<card-number>:           # int, globally unique, sequential from 1
  slug: <card-slug>      # matches card-slug frontmatter in the card file
  creates: [<path>, ...] # root-relative paths this card creates (empty list ok)
  modifies: [<path>, ...] # root-relative paths this card modifies (empty list ok)
  reads: [<path>, ...]   # root-relative paths this card reads for context
  depends-on: [<N>, ...] # card numbers this card depends on; [] for no deps
```

**Rules:**
- `creates:` and `modifies:` must not **both** be empty for any card (`plan_validator` checks this).
- `reads:` must exactly match the `Reads:` field in the corresponding card file.
- `depends-on:` references must point to lower-numbered cards (no forward references).
- All paths are **root-relative** (prefixed by `root:` to form full repo-relative paths).

### `card-NN-<slug>.md` — one card file per step

```markdown
---
kind: plan-card
card-number: 1
card-slug: add-dag-module
---

### Step 1: Create dag.py with topological sort

- **Creates:** `core/dag.py`
- **Modifies:** none
- **Reads:** `core/plan_io.py`
- **Requirements:**
  - Requirement 1 (specific, testable)
- **Explore:**
  - `core/plan_io.py` — module structure to follow.
- **depends-on:** []
- **TDD:** RED -> GREEN -> REFACTOR
- **Test approach:** unit
- **Key test scenarios:**
  - Happy: topological sort returns correct order.
  - Error: cycle detected raises ValueError.
- **Commit:** `feat(dag): add DAG builder with topological sort`
```

### Card file frontmatter fields (v3)

| Field | Required | Description |
|---|---|---|
| `kind` | yes | Must be `plan-card`. |
| `card-number` | yes | Integer matching the Card Index key. Globally unique, sequential. |
| `card-slug` | yes | Hyphenated slug matching the Card Index `slug:` field. |

### Card file body (v3)

The body contains a **single step card** using the same step card schema as v2 (see "Step Card Schema" below). The `Reads:` field in the card body must exactly match the `reads:` list in the Card Index.

### `root:` path resolution semantics

When `root:` is non-empty (e.g. `root: plugins/mill/scripts/millpy`):
- Paths in `creates:`, `modifies:`, and `reads:` in the Card Index are **root-relative**.
- Paths in `Creates:`, `Modifies:`, and `Reads:` in card files are **root-relative**.
- `plan_io.resolve_path(loc, relative)` prepends `root + "/"` to form a full repo-relative path.
- `plan_io.read_files_touched(loc)` returns full repo-relative paths (root prefix applied).

When `root:` is empty string:
- All paths are already full repo-relative paths.
- `resolve_path` returns the relative path unchanged.

**Example:** `root: plugins/mill/scripts/millpy`, `reads: [core/plan_io.py]` → full path `plugins/mill/scripts/millpy/core/plan_io.py`.

### Card numbering (v3)

Card numbering is **global and sequential starting at 1** with no gaps. `plan_validator` enforces sequential numbering with no gaps. The Planner assigns numbers in dependency order (a card's direct dependencies always have lower numbers).

### v3 Backward Compatibility

v3 detection takes priority when a `plan/` directory contains `card-*.md` files:
- `card-*.md` files in `plan/` → **v3**
- `NN-<slug>.md` batch files in `plan/` (no `card-*.md`) → **v2**
- `plan.md` file → **v1**

`plan_io.resolve_plan_path` handles this detection. All callers go through `plan_io` — no inline v1-vs-v2-vs-v3 branching at call sites.

### v3 Worked Example — two-card plan

**`00-overview.md`:**
```markdown
---
kind: plan-overview
task: Add DAG module
verify: python -m pytest plugins/mill/scripts/millpy/tests
dev-server: N/A
approved: false
started: 20260416-120000
root: plugins/mill/scripts/millpy
---

# Add DAG module

## Card Index

```yaml
1:
  slug: add-dag-module
  creates: [core/dag.py, tests/core/test_dag.py]
  modifies: []
  reads: [core/plan_io.py]
  depends-on: []
2:
  slug: update-plan-io
  creates: []
  modifies: [core/plan_io.py]
  reads: [core/plan_io.py, core/dag.py]
  depends-on: [1]
```

## All Files Touched

- core/dag.py
- tests/core/test_dag.py
- core/plan_io.py
```

**`card-01-add-dag-module.md`:**
```markdown
---
kind: plan-card
card-number: 1
card-slug: add-dag-module
---

### Step 1: Create dag.py with topological sort and test

- **Creates:** `core/dag.py`, `tests/core/test_dag.py`
- **Modifies:** none
- **Reads:** `core/plan_io.py`
- **Requirements:**
  - `build_dag(card_index: dict[int, dict]) -> dict[int, list[int]]`: returns adjacency list.
  - `topo_sort(dag) -> list[int]`: topological order, raises `ValueError` on cycle.
- **Explore:**
  - `core/plan_io.py` — module structure to follow.
- **depends-on:** []
- **TDD:** RED -> GREEN -> REFACTOR
- **Test approach:** unit
- **Key test scenarios:**
  - Happy: linear chain → correct order.
  - Error: cycle → ValueError.
- **Commit:** `feat(dag): add DAG builder with topological sort`
```

---

The plan is the autonomous-execution contract written by `mill-go` Phase: Plan and consumed by Thread B (the implementer-orchestrator) per `implementer-brief.md`. It captures every decision and step needed to implement the task without further human interpretation.

**The plan is the authoritative scope for Thread B.** Thread B reads this file and the codebase; it has no access to the discussion conversation or to Thread A's reasoning beyond what is written here. Each step card must be self-contained at the card level (see "Atomicity Invariant" below).

## v2 Directory Layout

For all new tasks, `mill-go` Phase: Plan writes a `.mill/active/<slug>/plan/` directory:

```
.mill/active/<slug>/
├── plan/
│   ├── 00-overview.md
│   ├── 01-core.md
│   ├── 02-tasks-worktree.md
│   └── 03-backends.md
├── discussion.md
└── status.md
```

Filename convention `NN-<slug>.md`: two-digit prefix for filesystem sort, hyphenated slug. `mill-go` reads the `batch-name:` frontmatter field — renames are safe.

## `00-overview.md` — the shared backbone

```markdown
---
kind: plan-overview
task: <task title>
verify: <build/test command, or "N/A">
dev-server: <dev-server command, or "N/A">
approved: false
started: <UTC YYYYMMDD-HHMMSS>
batches: [core, tasks-worktree, backends]
---

# <Task Title>

## Context
(Problem statement, approach framing, high-level what-and-why.)

## Shared Constraints
(Invariants that apply across every batch unless explicitly overridden.
 One-line rule per bullet + brief rationale.)

## Shared Decisions

### Decision: <title>
**Why:** Reasoning behind the choice.
**Alternatives rejected:** What else was considered and why not.

## Batch Graph

```yaml
batches:
  core:
    depends-on: []
    summary: "Skeleton + core utilities."
  tasks-worktree:
    depends-on: [core]
    summary: "tasks/ and worktree/ modules."
  backends:
    depends-on: [core]
    summary: "Backend Protocol + implementations."
```

## All Files Touched

- plugins/mill/scripts/millpy/core/foo.py
- plugins/mill/scripts/millpy/core/bar.py
```

### `00-overview.md` frontmatter fields

| Field | Required | Description |
|---|---|---|
| `kind` | yes | Must be `plan-overview`. |
| `task` | yes | Task title from `tasks.md`. |
| `verify` | yes | Build/test command used by Thread B. |
| `dev-server` | yes | Dev-server command, or the literal `N/A`. |
| `approved` | yes | Starts `false`; Plan Review sets it `true`. Thread B refuses to spawn if `false`. |
| `started` | yes | UTC timestamp generated via `date -u +"%Y%m%d-%H%M%S"`. Used by Phase: Setup for the staleness window. |
| `batches` | yes | Inline YAML list of batch slugs in filename order. `batches: [core, tasks-worktree, backends]` — square-bracket form only. |

### Sections in `00-overview.md`

- **`# <Task Title>`** — single h1 matching the task title from `tasks.md`.
- **`## Context`** — problem statement and approach framing. Decisions that affect more than one batch go here as `### Decision:` subsections (same format as `discussion.md`).
- **`## Shared Constraints`** — invariants enforced across every batch. Reviewers and Thread B read these first.
- **`## Shared Decisions`** — one `### Decision: <title>` subsection each. Batch files reference these instead of duplicating them.
- **`## Batch Graph`** — YAML fenced block with a `batches:` dict. Each key is a batch slug mapped to `depends-on: [...]` and `summary: "..."`. The graph must be acyclic (`plan_validator` checks this).
- **`## All Files Touched`** — flat bulleted list of every file any batch creates, modifies, or reads. Used by:
  - `mill-go` Phase: Setup staleness check.
  - The whole-plan reviewer's "read all source files" step.
  - Thread B's exploration anchor in Phase: Implement.

The overview file is never directly implemented. It has no step cards. It is read by every reviewer and every implementer.

## `NN-<slug>.md` — one batch file per batch

```markdown
---
kind: plan-batch
batch-name: core
batch-depends: []
approved: false
---

# Batch 01: core utilities

## Batch-Specific Context
(Decisions specific to this batch only. Most batches have none — they inherit
 from the overview's Shared Constraints and Shared Decisions. This heading must
 be present even if the section body is empty.)

## Batch Files

- plugins/mill/scripts/millpy/core/plan_io.py
- plugins/mill/scripts/millpy/tests/core/test_plan_io.py

## Steps

### Step 3: Create plan_io.py module with tests

- **Creates:** `plugins/mill/scripts/millpy/core/plan_io.py`, `plugins/mill/scripts/millpy/tests/core/test_plan_io.py`
- **Modifies:** none
- **Reads:** `plugins/mill/scripts/millpy/core/config.py`, `plugins/mill/scripts/millpy/core/log_util.py`
- **Requirements:**
  - Requirement 1 (specific, testable)
  - Requirement 2
- **Explore:**
  - `plugins/mill/scripts/millpy/core/config.py` — for the module style and `_parse_yaml_mapping` reuse.
- **depends-on:** []
- **TDD:** RED -> GREEN -> REFACTOR
- **Test approach:** unit
- **Key test scenarios:**
  - Happy: resolve v2 directory → returns PlanLocation with kind="v2".
  - Error: directory exists but missing 00-overview.md → raises ValueError.
  - Edge: both plan.md and plan/ present → v2 wins, logs INFO warning.
- **Commit:** `feat(plan_io): add plan_io module for v1/v2 plan location and read abstractions`
```

### Batch file frontmatter fields

| Field | Required | Description |
|---|---|---|
| `kind` | yes | Must be `plan-batch`. |
| `batch-name` | yes | Slug matching the overview's `batches:` list entry. |
| `batch-depends` | yes | Inline list of batch slugs this batch depends on. `batch-depends: []` for independent batches. |
| `approved` | yes | Starts `false`. Present for forward compatibility — W2 writes approval only to the overview. |

### Sections in `NN-<slug>.md`

- **`# Batch NN: <description>`** — h1 title for the batch.
- **`## Batch-Specific Context`** — decisions scoped to this batch only. **The heading must be present even if empty.**
- **`## Batch Files`** — strict subset of the overview's `## All Files Touched` that this batch touches.
- **`## Steps`** — the step cards for this batch (see "Step Card Schema" below).

## Step Card Schema (v2)

Every v2 step card must contain these fields, in this order:

```markdown
### Step N: <short description>

- **Creates:** `path/to/new/file` (or `none`)
- **Modifies:** `path/to/existing/file` (or `none`)
- **Reads:** `path/to/file/read/for/context` (one path per bullet, or `none`)
- **Requirements:**
  - Requirement 1
  - Requirement 2
- **Explore:**
  - `path/to/exemplar/file` — what to learn from it and why
- **depends-on:** [N, M] (or `[]` for no dependencies)
- **TDD:** RED -> GREEN -> REFACTOR (omit if not test-driven)
- **Test approach:** unit / integration / documentation review / smoke-test
- **Key test scenarios:**
  - Happy: <observable behavior on the success path>
  - Error: <observable behavior on the failure path>
  - Edge: <boundary condition or unusual input>
- **Commit:** `type: commit message in conventional-commit form`
```

### Field rules (v2)

- **Creates:** new files this step adds. Use `none` if the step only modifies existing files.
- **Modifies:** existing files this step changes. Use `none` if purely additive. A card with both `Creates: none` and `Modifies: none` is a structural violation.
- **Reads:** NEW in v2. Existing files the card reads for context — imports, helpers, exemplars, types — OR that a reviewer needs to verify the card. Must be complete. Every path in `Explore:` must also appear in `Reads:` (`plan_validator` checks this). A card that imports from file X but does not list X in `Reads:` is a BLOCKING plan-review finding.
- **Explore:** purpose-driven exploration targets. Each entry pairs a path with **what to learn from it and why**. Every `Explore:` path must be a subset of `Reads:`. Paths are identified by the parser as backtick-wrapped tokens that **either contain `/` or end with a known source-file extension** (`.py`, `.md`, `.json`, `.yaml`, `.yml`, `.toml`, `.sh`, `.ps1`, `.ts`, `.js`, `.tsx`, `.jsx`). Other backtick-wrapped tokens in the commentary — code identifiers like `_CONSTANT` or `do_thing()`, placeholders like `<TOKEN>` or `{foo}` — are ignored for the subset check, so you can freely cite symbols alongside the path.
- **depends-on:** NEW in v2. List of prior step numbers this card depends on. Inline-list form: `[3, 5]` or `[]`. References must resolve to step numbers that precede this card (within this batch or in batches listed in `batch-depends:`). Written by the planner; read by W3's DAG executor.
- **TDD:** present only when the step is test-driven.
- **Test approach:** what kind of testing applies. Documentation steps use `documentation review`.
- **Key test scenarios:** at minimum one Happy and one Error or Edge.
- **Commit:** exact commit message in conventional-commit form.

### Card numbering

Card numbering is **global across batches**. Batch `01-core` contains cards 1–7, batch `02-tasks-worktree` starts at 8, etc. Within a batch, cards are numbered in filename order, not dependency order. `plan_validator` enforces global uniqueness with no gaps.

### `touches-files:` is derived, not declared

v2 cards do NOT have a `touches-files:` field. The write-set (`Creates ∪ Modifies`) and read-set (`Reads`) are declared separately. Tooling derives `touches-files` as needed — no "forgot to update one of two" failure mode.

## Atomicity Invariant

**Each step card must be implementable in isolation by a fresh agent that has read only the card and the repo.**

### The extraction test

> Rip out one step card. Hand it (and only it) to a fresh agent that has not read the rest of the plan. Tell the agent to implement that step. Can it succeed?

If the answer is "no, it would need to read another step's `## Decisions` for context" — the card is not atomic enough. Rewrite it.

### What the invariant requires of every card

- **Absolute repo-rooted paths** in `Creates:`, `Modifies:`, and `Reads:`. No relative paths, no shorthand.
- **Pattern exemplars in `Explore:`**, with file paths AND what the agent should learn from them.
- **Self-contained `Requirements:`**. A requirement that reads "follow the pattern from Step 3" fails the extraction test. Inline the pattern or restate it.
- **Self-contained `Commit:` message**. No back-references to other commits.

### Verbosity is the feature

Repetition across step cards (the same exemplar path cited in multiple `Explore:` lists, the same constraint restated in multiple `Requirements:` blocks) is acceptable and expected. Compression and DRY are anti-goals here.

## Step Granularity

Each step must touch a small, reviewable scope. Bundling unrelated file operations in a single step is forbidden. Examples of violations:

- A step that creates a new doc and rewrites an unrelated skill in one commit.
- A step whose `Modifies:` list spans more than ~5 unrelated paths.

When a step's natural scope is large, split it into smaller steps. Each split step gets its own commit and its own atomic step card.

## Backwards Compatibility

- If `.mill/active/<slug>/plan/` (directory) exists **and** contains `card-*.md` files → **v3**.
- If `.mill/active/<slug>/plan/` (directory) exists **without** `card-*.md` files → **v2**.
- Else if `.mill/active/<slug>/plan.md` (file) exists → **v1**.
- Both `plan/` and `plan.md` present → **v2 or v3 wins**; an INFO-level warning is logged. Never halts.
- Neither → `plan_io.resolve_plan_path` returns `None`.

`plan_io.py` (the reader shim) handles this resolution. All callers go through `plan_io` — no inline v1-vs-v2-vs-v3 branching at call sites.

## v2 Worked Examples

### Example `00-overview.md` (two-batch plan)

```markdown
---
kind: plan-overview
task: Add plan_io module
verify: python -m pytest plugins/mill/scripts/millpy/tests
dev-server: N/A
approved: false
started: 20260415-120000
batches: [core, tests]
---

# Add plan_io module

## Context

This task adds `plan_io.py` to handle v1/v2 plan path resolution.

### Decision: v2 wins on both-present
**Why:** Prevents confusion when a migration is partially complete.
**Alternatives rejected:** Halt on both-present (overly strict).

## Shared Constraints

- Use `log()` from `millpy.core.log_util` — do NOT import Python's stdlib `logging`.
- All paths use forward slashes (Path.as_posix()) for Windows compatibility.

## Shared Decisions

(None beyond those in ## Context.)

## Batch Graph

```yaml
batches:
  core:
    depends-on: []
    summary: "plan_io module implementation."
  tests:
    depends-on: [core]
    summary: "Unit tests for plan_io."
```

## All Files Touched

- plugins/mill/scripts/millpy/core/plan_io.py
- plugins/mill/scripts/millpy/tests/core/test_plan_io.py
```

### Example `01-core.md` (two cards)

```markdown
---
kind: plan-batch
batch-name: core
batch-depends: []
approved: false
---

# Batch 01: plan_io implementation

## Batch-Specific Context

(None — all constraints in the overview apply.)

## Batch Files

- plugins/mill/scripts/millpy/core/plan_io.py

## Steps

### Step 1: Create plan_io.py with PlanLocation dataclass and resolve_plan_path

- **Creates:** `plugins/mill/scripts/millpy/core/plan_io.py`
- **Modifies:** none
- **Reads:** `plugins/mill/scripts/millpy/core/config.py`, `plugins/mill/scripts/millpy/core/log_util.py`
- **Requirements:**
  - Dataclass `PlanLocation(kind: Literal["v1","v2"], path: Path, overview: Path|None, batches: list[Path])`.
  - `resolve_plan_path(task_dir: Path) -> PlanLocation | None` — v2 if `task_dir/"plan"` is a directory, v1 if `task_dir/"plan.md"` is a file, both → v2 + INFO warning, neither → None.
- **Explore:**
  - `plugins/mill/scripts/millpy/core/config.py` — module style, `_parse_yaml_mapping` for frontmatter parsing reference.
  - `plugins/mill/scripts/millpy/core/log_util.py` — `log()` signature to use for the both-present warning.
- **depends-on:** []
- **TDD:** RED -> GREEN -> REFACTOR
- **Test approach:** unit
- **Key test scenarios:**
  - Happy: `task_dir` has `plan/` with `00-overview.md` → `PlanLocation(kind="v2", ...)`.
  - Edge: both present → v2 wins, INFO warning logged to stderr (check via capsys, not caplog).
  - Edge: neither present → `None`.
- **Commit:** `feat(plan_io): add PlanLocation dataclass and resolve_plan_path`

### Step 2: Add read helpers to plan_io.py

- **Creates:** none
- **Modifies:** `plugins/mill/scripts/millpy/core/plan_io.py`
- **Reads:** `plugins/mill/scripts/millpy/core/plan_io.py`, `plugins/mill/doc/formats/plan.md`
- **Requirements:**
  - `read_plan_content(loc) -> str` — v1: file text verbatim; v2: concatenated with `"=== <path> ===\n\n"` headers and `"\n\n---\n\n"` separators, no trailing separator on the last file.
  - `read_files_touched(loc) -> list[str]` — v1: parse `## Files` bullets; v2: parse `## All Files Touched` bullets in `00-overview.md`.
  - `read_approved(loc) -> bool`, `write_approved(loc, value) -> None`.
  - `read_started(loc) -> str`, `read_verify(loc) -> str`, `read_dev_server(loc) -> str | None`.
- **Explore:**
  - `plugins/mill/scripts/millpy/core/plan_io.py` — the PlanLocation structure from Step 1 to dispatch on `loc.kind`.
- **depends-on:** [1]
- **Test approach:** unit
- **Key test scenarios:**
  - Happy v2: `read_plan_content` returns `=== plan/00-overview.md ===\n\n...\n\n---\n\n=== plan/01-core.md ===\n\n...` (final file without trailing separator).
  - Happy: `write_approved` flips the frontmatter field without touching any other line.
  - Edge: `read_dev_server` returns `None` for `dev-server: N/A`.
- **Commit:** `feat(plan_io): add read/write helpers`
```

## Relationship to Other Documents

- `plan_io.py` — the reader shim that resolves v1 vs v2 vs v3 paths. All callers use this module; no inline path logic.
- `plan_validator.py` — the structural checker. Called at plan-write time (by `mill-plan`) and at pre-dispatch time (by `spawn_reviewer.py`).
- `plan-review.md` — the reviewer protocol. Reviewer prompts are materialized per-mode (v1 / v2 per-batch / v2 whole-plan / v3 per-card) using sentinel `N/A` tokens.
- `implementer-brief.md` — Builder's consumer. Builder receives `<PLAN_PATH>` which may be a file (v1) or directory (v2/v3) and uses `plan_io` to read it.

---

## v1 Legacy Format

v1 uses a single `.mill/active/<slug>/plan.md` file. In-flight v1 tasks are read via `plan_io.resolve_plan_path` which dispatches on `loc.kind == "v1"`. New tasks always use v2.

### v1 Frontmatter

```yaml
---
verify: <build/test command, or "N/A">
dev-server: <dev server command, or "N/A">
approved: false
started: <UTC YYYYMMDD-HHMMSS>
---
```

### v1 Mandatory Sections

`## Context`, `## Files`, `## Steps`.

### v1 Step Card Schema

```markdown
### Step N: <short description>

- **Creates:** `path` (or `none`)
- **Modifies:** `path` (or `none`)
- **Requirements:** ...
- **Explore:** `path` — what to learn
- **TDD:** RED -> GREEN -> REFACTOR (optional)
- **Test approach:** ...
- **Key test scenarios:** ...
- **Commit:** `type: message`
```

v1 cards have no `Reads:` field and no `depends-on:` field. The `plan_validator` v2-only checks (`Explore:` ⊆ `Reads:`, card numbering uniqueness, `batch-depends:` resolution) do not apply to v1 plans. Atomicity invariant and step granularity heuristics are unchanged from v1 to v2.
