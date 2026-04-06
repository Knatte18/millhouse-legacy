# Discussion File Format

The discussion file is the handoff document between `mill-start` (interactive) and `mill-go` (autonomous). It captures everything from the discussion phase that `mill-go` needs to write an implementation plan in a fresh session.

**The discussion file is the authoritative scope for `mill-go` — not the original task description.** Scope evolves during discussion. `mill-go` reads only this file and the codebase; it has no access to the conversation history from `mill-start`.

## File Location

`_millhouse/scratch/discussion.md`

`mill-go` discovers this file via the `discussion:` field in `_millhouse/scratch/status.md`.

## Frontmatter

```yaml
---
task: <task title>
branch: <current branch name>
worktree: <absolute path to current worktree>
parent: <parent branch name>
timestamp: <UTC YYYY-MM-DD-HHMMSS>
---
```

- `worktree:` must be written using the output of `git rev-parse --show-toplevel` (forward-slash, even on Windows). `mill-go` compares this value against its own working directory to detect worktree mismatches.
- `parent:` is the parent branch for merge operations. Required as a fallback for `mill-merge` and plan-stale revert when `_millhouse/config.yaml` is absent.
- The discussion file does NOT have an `approved:` field. The completion signal is `phase: discussed` in `status.md`.

## Mandatory Sections

### `## Problem`

The evolved problem statement as understood after discussion. Not a copy of the original task description — this reflects what was clarified, narrowed, or expanded during the conversation.

### `## Approach`

The selected approach, including:
- **What:** concise description of the solution
- **Why:** reasoning behind the choice
- **Alternatives rejected:** what else was considered and why not

### `## Decisions`

One subsection per significant design choice made during discussion:

```markdown
### Decision: <title>
**Why:** Reasoning behind the choice.
**Alternatives rejected:** What else was considered and why not.
```

These decisions are what the plan reviewer checks against. Omitting them means reviewers review in a vacuum.

### `## Scope`

Explicit boundaries:
- **In scope:** what this task covers
- **Out of scope:** what is explicitly excluded

### `## Constraints`

Hard invariants that the implementation must respect:
- Constraints from `CONSTRAINTS.md` (if it exists in the repo root)
- Constraints discovered during discussion (performance, compatibility, existing patterns)

If no constraints exist, write: "No constraints identified."

### `## Technical Context`

Relevant codebase findings from the Explore phase:
- Existing patterns that the implementation should follow
- Key files and modules involved
- Dependencies and integration points
- Anything discovered that affects the design

### `## Testing Strategy`

At minimum:
- Whether tests will be written and what kind (unit / integration / e2e)
- TDD candidates (which modules or features)
- Key test scenarios per module (happy path, error paths, edge cases)

Scenario-level detail is a bonus — the plan reviewer fills in gaps during plan review.

### `## Q&A Log`

All questions asked during the discussion phase and their answers. Format:

```markdown
**Q:** <question asked>
**A:** <answer given>
```

This preserves the full reasoning chain. `mill-go` can reference specific Q&A entries when writing the plan.

### `## Config`

```markdown
- **Verify:** <build/test command, or "N/A">
- **Dev server:** <dev server command, or "N/A">
```

These values are copied into the plan frontmatter by `mill-go`.

## status.md Schema

After `mill-start` completes (Phase: Handoff), `status.md` must contain:

```yaml
discussion: _millhouse/scratch/discussion.md
phase: discussed
task: <task-title>
parent: <parent-branch>
```

- `phase: discussed` is the completion sentinel. `mill-go` checks for exactly this value on entry to confirm `mill-start` completed normally.
- `parent:` is the fallback for `mill-merge` and plan-stale revert when `_millhouse/config.yaml` is absent.

After `mill-go` Plan Review completes and sets `approved: true` in the plan frontmatter, `mill-go` adds:

```yaml
plan: _millhouse/scratch/plans/<filename>.md
```

The `approved:` field lives in the plan frontmatter, not in `status.md`.
