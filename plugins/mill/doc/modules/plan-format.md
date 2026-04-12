# Plan File Format

The plan file is the autonomous-execution contract written by `mill-go` Phase: Plan and consumed by Thread B (the implementer-orchestrator) per `implementer-brief.md`. It captures every decision and step needed to implement the task without further human interpretation.

**The plan file is the authoritative scope for Thread B.** Thread B reads this file and the codebase; it has no access to the discussion conversation or to Thread A's reasoning beyond what is written here. The plan must be self-contained at the document level and **each step card must be self-contained at the card level** (see "Atomicity Invariant" below).

## File Location

`_millhouse/task/plan.md`

`mill-go` discovers this file via the `plan:` field in `_millhouse/task/status.md`. Thread B receives the path through its spawn brief.

## Frontmatter

```yaml
---
verify: <build/test command, or "N/A">
dev-server: <dev server command, or "N/A">
approved: false
started: <UTC YYYYMMDD-HHMMSS>
---
```

- `verify:` is copied from the discussion file's `## Config` section. Used by Thread B for the test baseline and the full verification step.
- `dev-server:` is copied from the same section. Optional reference for UI tasks.
- `approved:` starts as `false`. Plan Review flips it to `true` when the reviewer (or the orchestrator after fixer rounds) is satisfied. Thread B refuses to spawn if `approved: false`.
- `started:` must be generated via shell `date -u +"%Y%m%d-%H%M%S"` (see `@mill:cli` timestamp rules — never guess timestamps). Used by `mill-go` Phase: Setup to compute the staleness check window: any commit to a file in `## Files` newer than this timestamp triggers the staleness halt.

## Mandatory Sections

### `# <Task Title>`

Single h1, matches the task title from `tasks.md`.

### `## Context`

Summary of the problem and what was discussed. This is what reviewers and Thread B read first.

Inside `## Context`, one `### Decision: <title>` subsection per significant design choice. Each decision must contain:

```markdown
### Decision: <title>
**Why:** Reasoning behind the choice.
**Alternatives rejected:** What else was considered and why not.
```

These are copied from the discussion file's `## Decisions` section. The plan reviewer checks `Why:` and `Alternatives rejected:` for completeness — omitting them means reviewers review in a vacuum.

### `## Files`

Bullet list of every file the plan touches (creates, modifies, or deletes). Used by:

- `mill-go` Phase: Setup staleness check (any commit to these files since `started:` triggers a halt).
- The plan-reviewer's "read all source files referenced in the plan's `## Files` section" step.
- Thread B's exploration anchor in Phase: Implement.

Use repo-relative paths (no leading `/`, no `./` prefix).

### `## Steps`

The implementation steps, in execution order. Each step is one `### Step N: <description>` heading followed by a step card (see "Step Card Schema" below).

Steps are 1-indexed and execute sequentially. Thread B does not parallelize.

## Step Card Schema

Every step card must contain these fields, in this order:

```markdown
### Step N: <short description>

- **Creates:** `path/to/new/file` (or `none`)
- **Modifies:** `path/to/existing/file` (or `none`)
- **Requirements:**
  - Requirement 1 (specific, testable, and complete enough to implement without further interpretation)
  - Requirement 2
- **Explore:**
  - `path/to/exemplar/file` — what to learn from it and why
  - `path/to/related/file` — what to look for and why
- **TDD:** RED -> GREEN -> REFACTOR (omit if not test-driven)
- **Test approach:** unit / handler-level / browser / documentation review / smoke-test
- **Key test scenarios:**
  - Happy: <observable behavior on the success path>
  - Error: <observable behavior on the failure path>
  - Edge: <boundary condition or unusual input>
- **Commit:** `type: commit message in conventional-commit form`
```

### Field rules

- **Creates:** the new files this step adds. Use `none` if the step only modifies existing files. A step that is purely additive (only `Creates:`) is valid; in that case `Modifies:` must read `none`.
- **Modifies:** the existing files this step changes. Use `none` if the step is purely additive. A step with both `Creates: none` and `Modifies: none` is a structural violation — it does nothing.
- **Requirements:** the contract for the step. Each requirement must be specific enough to implement and testable enough that a reviewer can decide whether the diff meets it. Vague language ("handle errors properly", "make it fast") is not a requirement.
- **Explore:** purpose-driven exploration targets. Each entry pairs a path with **what to learn from it and why**. Generic ("read the codebase") fails. Specific ("read `plugins/mill/doc/modules/discussion-review.md` for the prompt-template format we are mirroring") passes.
- **TDD:** present only when the step is test-driven. When present, Thread B follows RED → GREEN → REFACTOR strictly: write the failing test first, confirm it fails, implement minimum code to pass, refactor with tests green.
- **Test approach:** what kind of testing applies to this step. Documentation steps use `documentation review`. Script-only steps use `smoke-test` (manual invocation) or `structural review`.
- **Key test scenarios:** at minimum one Happy and one Error or Edge. Reviewers flag happy-only test coverage as BLOCKING.
- **Commit:** the exact commit message Thread B will use. Conventional commit form. Used by Thread B for both committing and for the Post-Setup resume sub-protocol's git-log-based step detection.

## Atomicity Invariant

**Each step card must be implementable in isolation by a fresh agent that has read only the card and the repo.**

This is the key discipline that distinguishes an atomic plan from a "context-shared" plan. The plan as a whole still has `## Context` and `## Decisions` for human review and reviewer evaluation, but **each step card must survive the extraction test**.

### The extraction test

> Rip out one step card. Hand it (and only it) to a fresh agent that has not read the rest of the plan. Tell the agent to implement that step. Can it succeed?

If the answer is "no, it would need to read another step's `## Decisions` for context" or "no, the path in `Modifies:` is ambiguous without the `## Files` list" — the card is **not atomic enough**. Rewrite it.

### What the invariant requires of every card

- **Absolute repo-rooted paths** in `Creates:` and `Modifies:`. No relative paths, no shorthand. `plugins/mill/doc/modules/plan-format.md` — not `plan-format.md` and not `./plan-format.md`.
- **Pattern exemplars in Explore:**, with file paths AND what the agent should learn from them. The agent needs to know which existing pattern to mirror without reading every other step.
- **Self-contained Requirements.** A requirement that reads "follow the pattern from Step 3" fails the extraction test. Inline the pattern or restate it.
- **Self-contained Commit message.** No back-references to other commits.

### Verbosity is the feature

Repetition across step cards (the same exemplar path cited in multiple `Explore:` lists, the same constraint restated in multiple `Requirements:` blocks) is acceptable and expected. The whole point is to let a fresh agent read one card and implement without referencing other cards. Compression and DRY are anti-goals here.

## Step Granularity

Each step must touch a small, reviewable scope. Bundling unrelated file operations in a single step is forbidden — flag as a structural violation. Examples of violations:

- A step that creates a new doc and rewrites an unrelated skill in one commit.
- A step that modifies five files in five different subdirectories with no shared theme.
- A step whose `Modifies:` list spans more than ~5 unrelated paths.

`validation.md` documents this heuristic. Reviewers enforce it during plan review.

When a step's natural scope is large, split it into smaller steps with explicit ordering. Each split step gets its own commit, its own test scenarios, and its own atomic step card.

## Relationship to Other Documents

- The plan is fed by **`discussion-format.md`** (the discussion file). `mill-go` Phase: Plan reads the discussion to write the plan.
- The plan is consumed by **`implementer-brief.md`** (Thread B's prompt). Thread B reads the plan to implement.
- The plan is reviewed via **`plan-review.md`** (the reviewer protocol). The review-only reviewer reads the plan independently.
- Validation rules for plan structure live in **`validation.md`** (`## plan.md` section).
- The two-thread architecture and per-phase model resolution are documented in **`overview.md`**.

## Worked Example: One Atomic Step Card

```markdown
### Step 7: Create spawn-agent.ps1

- **Creates:** `plugins/mill/scripts/spawn-agent.ps1`
- **Modifies:** none
- **Requirements:**
  - PowerShell script. Param block: `[Parameter(Mandatory=$true)][ValidateSet('reviewer','implementer')][string]$Role`, `[Parameter(Mandatory=$true)][string]$PromptFile`, `[Parameter(Mandatory=$true)][string]$ProviderName`, `[int]$MaxTurns`, `[string]$WorkDir = $PWD`.
  - Defaults: `-MaxTurns` defaults by role (`reviewer = 20`, `implementer = 200`).
  - Synchronous from the script's perspective. No `Start-Process`, no `Start-Job`, no detachment. Backgrounding is the Bash tool's responsibility.
  - Backend dispatch: `opus`, `sonnet`, `haiku` → claude backend (uses `claude -p --model <name>`). Anything else → exit 3 with stderr "[spawn-agent] Provider '<name>' not implemented in this task."
  - Claude backend pipes the prompt file to `claude -p --model <model> --max-turns <max> --output-format json` via stdin. Captures stdout, parses JSON, extracts `result`. Empty/unparseable result → exit 1.
  - Stdout reserved for the final JSON line. All informational logging goes to stderr.
- **Explore:**
  - `git show 0d15316:plugins/mill/scripts/spawn-agent.ps1` — lift the stdin-pipe-to-claude pattern and the prompt-file-existence check.
  - `plugins/mill/scripts/mill-spawn.ps1` — local PowerShell style: param block, `$ErrorActionPreference`, error handling.
- **Test approach:** smoke-test (manual invocation), structural review.
- **Key test scenarios:**
  - Happy: `powershell.exe -File plugins/mill/scripts/spawn-agent.ps1 -Role reviewer -PromptFile <fake> -ProviderName ollama-7b` exits 3 with the "not implemented" stderr message.
  - Error: missing `-PromptFile` causes a parameter-binding error (exit non-zero).
  - Edge: stdout when invoked with `-ProviderName ollama-7b` is empty — the not-implemented error goes to stderr only.
- **Commit:** `feat: add spawn-agent.ps1 unified subagent spawn script`
```

This card is implementable by a fresh agent: paths are absolute, exemplars cite specific files with what to learn, requirements are testable, scenarios cover happy + error + edge, commit message is verbatim.
