# Coherence & Quality

## Current Approach

Helm does NOT use Autoboard's multi-agent coherence audit system. Instead, codebase consistency is enforced through:

1. **Codeguide** — CC reads the Overview and module docs before implementing, so it knows what utilities and patterns exist. This prevents reimplementation of existing functionality.
2. **Code reviewer** — explicitly checks for utility duplication (greps codebase for similar functions) and pattern consistency (new code follows existing conventions). Reimplementation of existing utilities is BLOCKING.
3. **Knowledge curation** — captures patterns established by prior tasks, so subsequent tasks follow them.
4. **Decisions register** — records *why* architectural choices were made, preventing contradictory decisions.
5. **Constraints** — repo-level hard invariants in `CONSTRAINTS.md` (repo root). Injected in all agents and reviewers, always blocking. Covers domain rules that code must never violate (e.g. coordinate system boundaries, type restrictions). See [constraints.md](constraints.md).

## Why Not Multi-Agent Coherence Audits

Autoboard uses 13 parallel dimension agents that each read the full codebase. This is:
- Expensive — 13 agents × full codebase scan = massive token cost
- Designed for parallelism — catches cross-session drift between agents that can't see each other's work
- Unnecessary for Helm — sequential execution within a worktree means each task sees prior tasks' commits

Helm's code reviewer with codeguide context catches the same issues at lower cost: it knows what exists (codeguide), it checks the diff for duplication (grep), and it verifies pattern consistency.

## Future Consideration

If experience shows that code review misses cross-codebase issues, a lightweight single-agent audit could be added to `helm-merge` (for merges to main only). This would be one Agent with targeted grep operations, not 13 parallel full-codebase scans.

## Quality Dimensions

Not used. Helm relies on existing always-on skills (`code:code-quality`, `code:testing`, `code:linting`) which are available in every CC session. Autoboard's dimensions exist because its headless sessions don't have access to general skills — Helm's sessions do.
