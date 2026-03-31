# Helm Design Review — Round 3

Review the Helm design documents and report issues, gaps, and strengths.

## What is Helm?

Helm is a new Claude Code plugin for worktree-based task orchestration. Interactive design phase (`helm-start`), autonomous execution with self-review (`helm-go`), cross-worktree parallelism via separate VS Code windows. GitHub Projects V2 as the sole backlog.

## Read These Files

### Helm design (the thing you're reviewing)
1. `C:\Code\millhouse\plugins\helm\doc\overview.md` — read first
2. All files in `C:\Code\millhouse\plugins\helm\doc\modules\` — read all of them
3. `C:\Code\millhouse\plugins\helm\doc\TODO.md` — remaining items

### Previous reviews (understand what was already found and fixed)
4. `C:\Code\millhouse\plugins\helm\doc\reviews\review-02-result.md` — round 2 findings

### Source material
5. Autoboard repo at `C:\Code\autoboard` — key files:
   - `README.md`, `CLAUDE.md`
   - `skills/session-workflow/SKILL.md`, `skills/run/SKILL.md`, `skills/brainstorm/SKILL.md`
   - `skills/receiving-review/SKILL.md`, `skills/coherence-audit/SKILL.md`, `skills/audit/SKILL.md`
   - `skills/merge/SKILL.md`, `skills/knowledge/SKILL.md`, `skills/failure/SKILL.md`
   - `agents/plan-reviewer.md`, `agents/code-reviewer.md`
6. Taskmill at `C:\Code\millhouse\plugins\taskmill\` — key skills in `skills/*/SKILL.md`
7. Codeguide at `C:\Code\millhouse\plugins\codeguide\` — all skills in `skills/*/SKILL.md`
8. Conduct plugin at `C:\Code\millhouse\plugins\conduct\` — recently created, replaces orchestration
9. Testing skill at `C:\Code\millhouse\plugins\code\skills\testing\SKILL.md` — recently updated

### Context
10. `C:\Code\millhouse\CLAUDE.md` — repo structure
11. `C:\Users\henri\.claude\CLAUDE.md` — startup skills (now conduct:conversation + conduct:workflow)

## What Changed Since Round 2

All blocking issues and most gaps from round 2 were addressed:
- `helm-go` is now always autonomous. New worktrees use `helm-start`, not `helm-go`.
- Merge lock path-resolution specified with `git worktree list --porcelain`.
- Codeguide-update moved before commit in helm-go flow.
- `helm-setup` fully specified in kanban.md with exact GraphQL queries.
- Handoff brief format defined in plans.md.
- Receiving-review invocation is explicitly MANDATORY before reading findings.
- TDD RED enforcement is an implementation-time gate.
- Retry tracking in `_helm/scratch/status.md`.
- Quality dimension loading added to helm-go flow.
- Knowledge synthesis step added between tasks.
- Knowledge file naming: `<worktree-slug>-<timestamp>-<topic>.md`.
- Cross-platform notifications (Windows/macOS/Linux).
- `orchestration` plugin replaced by `conduct` (conversation + workflow).
- `code:testing` updated with coverage requirements, TDD discipline, shallow test prevention.

## Focus Areas for This Round

### Consistency check
- Read EVERY doc file. Check that all cross-references are correct.
- Verify `_helm/scratch/` is used consistently (not `.llm/`, not `_helm/status.md` without `scratch/`).
- Verify `conduct:conversation` and `conduct:workflow` are referenced correctly (not `orchestration:*`).
- Verify `helm-start` (not `helm-go`) is referenced for new worktrees everywhere.
- Check step numbering in skills.md helm-go flow — there were renumbering edits.

### Completeness
- Is every skill fully specified? Could an implementer build each skill from the doc alone?
- Are there implicit assumptions not stated? (e.g., "CC can run `code <path>`" — can it?)
- Is the `helm-setup` flow in kanban.md complete? Missing edge cases?
- Is the handoff brief format in plans.md sufficient for `helm-start` in a new worktree?

### Implementability
- For each skill: what's the first thing an implementer would get stuck on?
- Are there circular dependencies between skills?
- What's the minimum viable subset of Helm that could ship first?

### Architecture
- Is the `_helm/` directory structure sound? Tracked vs gitignored split?
- Is `_helm/config.yaml` doing too much? (worktree config + GitHub Projects IDs in one file)
- Is the conduct plugin correctly structured? Does the workflow skill belong there?

### What's missing?
- Any scenarios not covered? (user wants to abandon a worktree, user wants to move a task between worktrees, user wants to revert a plan)
- Any Autoboard patterns still worth adopting that Helm hasn't?
- Is there anything the `code:testing` update missed?

## Output Format

### Blocking Issues
For each:
- **What:** one sentence
- **Where:** which doc file and section
- **Why:** why it matters
- **Suggestion:** concrete fix

### Important Gaps
Same format.

### Minor Issues
Brief list.

### Strengths
What's well-designed or improved since round 2. Brief list.

### Recommendations
Ordered list of what to fix first, with reasoning.

Write your review to `C:\Code\millhouse\plugins\helm\doc\reviews\review-03-result.md`.
