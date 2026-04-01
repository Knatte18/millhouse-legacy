# Knowledge Curation

## Purpose

After each task, capture what was learned so subsequent tasks start with context instead of re-discovering it. Inspired by Autoboard's inter-layer knowledge curation.

## When Knowledge is Written

After each task completes in `helm-go`, before moving to the next task:

1. Write a knowledge entry to `_helm/knowledge/<worktree-slug>-<timestamp>-<topic>.md`. The worktree-slug prefix prevents filename collisions when child worktrees merge knowledge back to parent.
2. Post a summary to the GitHub issue as a comment.

## Content

Each knowledge entry captures:

```markdown
# Task: <title>

## Shared utilities created
- `src/lib/auth.ts` exports `authenticatedQuery(handler)` — wraps handlers with automatic userId injection

## Patterns established
- All API error responses use `AppError` with a reason string — do not throw raw Error objects

## Existing patterns discovered
- The project uses barrel exports in each feature directory — add an index.ts when creating a new feature folder

## Gotchas
- Convex validators don't support optional fields with defaults — must handle undefined explicitly
```

Categories (include only those with content):
- **Shared utilities created** — file paths, function signatures, usage examples
- **Patterns established** — conventions that future tasks should follow
- **Existing patterns discovered** — things already in the codebase that weren't obvious
- **Gotchas** — things that caused wasted time

## How Knowledge is Consumed

### Next task in same worktree

`helm-go` reads all entries in `_helm/knowledge/` before starting the next task. This provides accumulated context without re-exploring the codebase.

### Child worktree spawning

When `helm-start -w` creates a child worktree, relevant knowledge entries are included in the handoff brief (`_helm/scratch/briefs/handoff.md`). The brief contains synthesized content — not raw file references — because the child worktree may not have access to the parent's `_helm/knowledge/` directory.

### Merge to parent

`_helm/knowledge/` is tracked (not gitignored). When `helm-merge` merges the worktree branch back to parent, knowledge files travel with the merge automatically.

### Review agents

The code-reviewer Agent receives relevant knowledge as context — it needs to know what patterns were established to verify the implementation follows them.

## Knowledge Synthesis

When accumulated knowledge exceeds ~5 entries, `helm-go` should synthesize before passing to the next task:

1. Read all `_helm/knowledge/*.md` entries
2. Deduplicate (multiple tasks may discover the same pattern)
3. Resolve conflicts (if task A established one pattern and task B a contradictory one, pick the winner)
4. Write a consolidated `_helm/knowledge/summary.md`
5. Subsequent tasks read only the summary, not individual entries

This prevents context bloat as a worktree accumulates tasks.
