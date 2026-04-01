# Plans

## Format

Inspired by Autoboard's task manifest, scaled down for single-threaded execution.

```markdown
---
verify: npm install && npm test
dev-server: npm run dev
approved: false
started: 2026-04-01-120000
---

# Task Title

## Context
Summary of discussion and key design decisions.

## Quality dimensions
security, api-design, test-quality

## Files
- src/auth/oauth-client.ts
- src/auth/oauth-client.test.ts

## Steps

### Step 1: Create OAuth client wrapper
- **Creates:** `src/auth/oauth-client.ts`
- **Modifies:** (none)
- **Requirements:**
  - Wrap Google OAuth2 client
  - Handle token refresh automatically
- **Explore:**
  - How existing auth middleware validates tokens — for consistent token handling
- **TDD:** RED -> GREEN -> REFACTOR
- **Test approach:** unit
- **Key test scenarios:**
  - Happy: valid token -> authenticated session
  - Error: expired token -> refresh flow triggers
  - Edge: malformed token -> clean rejection with error message
- **Commit:** `feat: add OAuth client wrapper`

### Step 2: Add callback endpoint
...
```

## Fields

### Frontmatter

| Field | Purpose |
|-------|---------|
| `verify` | Build/test command. Run after each step and for full verification. |
| `dev-server` | Dev server command (for browser testing if applicable). |
| `approved` | Set to `true` by helm-start after plan review passes. helm-go refuses to execute unapproved plans. |
| `started` | UTC timestamp when discussion began. Used for staleness detection. |

### Per-step fields

| Field | Source | Purpose |
|-------|--------|---------|
| `Creates:` / `Modifies:` | Autoboard | Staleness check, review scope |
| `Requirements:` | Autoboard | Detailed requirements, replaces one-liners |
| `Explore:` | Autoboard | Purpose-driven exploration targets (what and why) |
| `TDD:` | Autoboard | Enforce RED → GREEN → REFACTOR cycle |
| `Test approach:` | Autoboard | `unit`, `handler-level`, or `browser` |
| `Key test scenarios:` | Autoboard | Happy/error/edge — reviewer verifies coverage |
| `Commit:` | Autoboard | Consistent commit message |

### Fields NOT adopted (not needed for sequential execution)

- `Depends on:` — implicit from step order
- `Complexity score` / `Effort level` — single thread, one model
- `Suggested Session:` — no sessions
- `Sessions table` — no sessions

## Plan Locking

Plans are freely editable during the `helm-start` review loop. After plan approval:

1. `helm-start` sets `approved: true` in frontmatter.
2. `helm-go` checks `approved: true` before executing. Refuses unapproved plans.
3. During `helm-go`, the plan is read-only. CC reads it for guidance but does not modify it.

This ensures the review gate is meaningful — the plan reviewed is the plan executed.

## Staleness Detection

Before implementing, `helm-go` checks if files listed in `## Files` have changed since the plan was written:

```bash
git log --since=<started-timestamp> -- <file1> <file2> ...
```

If changes are found: re-read affected files, notify user that the plan may need revision.

## Storage

Plans live in `_helm/scratch/plans/<timestamp>-<slug>.md` (gitignored via `_helm/scratch/`).

After plan approval, `helm-start` posts a summary of the plan (context + step list) as a comment on the GitHub issue. Not a file path — the actual content, since plan files are gitignored and won't survive worktree cleanup.

## Handoff Brief Format

When `helm-start -w` creates a worktree, it writes `_helm/scratch/briefs/handoff.md`. This is background context for the receiving `helm-start` session — not a plan, not an instruction.

```markdown
# Handoff: <task title>

## Issue
#<issue-number>: <title>

## Parent
Branch: <parent-branch>
Worktree: <parent-path>

## Discussion Summary
<Key points from the discussion so far. Decisions made, trade-offs considered,
approaches rejected and why. If no discussion happened, just the task description
from the GitHub issue body.>

## Knowledge from Parent
<Synthesized knowledge entries from parent's _helm/knowledge/.
Include: relevant utilities, patterns, conventions, gotchas.
If no knowledge: "No prior knowledge.">

## Relevant Codeguide Modules
<List of codeguide module docs relevant to this task, identified during
the parent's explore phase. If codeguide doesn't exist: omit this section.>

## Config
- Verify: <verify command from parent's config or plan>
- Dev server: <dev-server command, if applicable>
```

The receiving `helm-start` reads this brief for context, then runs its own explore + discuss + plan cycle with the user. The brief informs but does not constrain.
