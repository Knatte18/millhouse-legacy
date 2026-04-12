# Discussion File Format

The discussion file is the handoff document between `mill-start` (interactive) and `mill-go` (autonomous). It captures everything from the discussion phase that `mill-go` needs to write an implementation plan in a fresh session.

**The discussion file is the authoritative scope for `mill-go` — not the original task description.** Scope evolves during discussion. `mill-go` reads only this file and the codebase; it has no access to the conversation history from `mill-start`.

## File Location

`_millhouse/task/discussion.md`

`mill-go` discovers this file via the `discussion:` field in `_millhouse/task/status.md`.

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

- `timestamp:` must be generated via shell `date -u +"%Y%m%d-%H%M%S"` (see `@mill:cli` timestamp rules — never guess timestamps).
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

`status.md` uses fenced code blocks per `markdown-format.md`. After `mill-start` completes (Phase: Handoff), `status.md` must have this structure:

````markdown
# Status

```yaml
discussion: _millhouse/task/discussion.md
phase: discussed
task: <task-title>
task_description: |
  <multi-line task description>
parent: <parent-branch>
```

## Timeline

```text
discussing              2026-04-08T10:23:15Z
discussed               2026-04-08T11:00:00Z
```
````

- `phase: discussed` is the completion sentinel. `mill-go` checks for exactly this value in the YAML code block on entry to confirm `mill-start` completed normally.
- `parent:` is the fallback for `mill-merge` and plan-stale revert when `_millhouse/config.yaml` is absent.
- `task_description:` stores the task body text (migrated from tasks.md). Written by `mill-start` (in-place flow) and `mill-spawn.ps1` (worktree flow via template).

After `mill-go` Plan Review completes and sets `approved: true` in the plan frontmatter, `mill-go` adds to the YAML code block:

```yaml
plan: _millhouse/task/plan.md
```

The `approved:` field lives in the plan frontmatter, not in `status.md`.

### Valid phase values

`discussing`, `discussed`, `planned`, `implementing`, `testing`, `reviewing`, `blocked`, `pr-pending`, `complete`.

The `phase:` field is the authoritative source of truth for the current workflow phase.

## Timeline Section

`status.md` includes a `## Timeline` section with a ` ```text ``` ` fenced block that records chronological phase history. Each phase transition inserts a new line before the closing ` ``` ` of the text fence using the Edit tool:

````markdown
## Timeline

```text
discussing              2026-04-08T10:23:15Z
discussion-review-r1    2026-04-08T10:45:00Z
discussed               2026-04-08T11:00:00Z
planned                 2026-04-08T11:05:00Z
implementing            2026-04-08T11:10:00Z
step-1                  2026-04-08T11:15:00Z
step-2                  2026-04-08T11:30:00Z
testing                 2026-04-08T11:45:00Z
reviewing               2026-04-08T11:50:00Z
code-review-r1          2026-04-08T12:00:00Z
complete                2026-04-08T12:10:00Z
```
````

Rules:
- Format: `<phase-name>  <ISO-8601-timestamp>` (two spaces between name and timestamp).
- Timestamps must be generated via shell `date -u +"%Y-%m-%dT%H:%M:%SZ"` (see `@mill:cli` timestamp rules).
- New entries are inserted before the closing ` ``` ` of the timeline text block using the Edit tool (not `echo >>`).
- Review rounds get individual entries: `plan-review-r1`, `plan-fix-r1`, `code-review-r1`, `code-fix-r1`, etc.
- Implementation steps get entries: `step-1`, `step-2`, etc.
- Unstarted phases have no entry (no `~` placeholders).
- The timeline is history, not current state. The `phase:` field in the YAML code block is the authoritative current phase.
