# Helm Design Review — Round 2

Review the Helm design documents and report issues, gaps, and strengths.

## What is Helm?

Helm is a new Claude Code plugin for worktree-based task orchestration. It combines:
- **Taskmill** (author's current system) — human-in-the-loop workflow
- **Autoboard** (Willie Tran) — autonomous execution, review gates, coherence audits
- **Motlin** (Craig Motlin) — plugin structure conventions

Core idea: interactive design phase (`helm-start`), autonomous execution with self-review (`helm-go`), cross-worktree parallelism via separate VS Code windows.

## Read These Files

### Helm design (the thing you're reviewing)
1. `C:\Code\millhouse\plugins\helm\doc\overview.md` — read first
2. All files in `C:\Code\millhouse\plugins\helm\doc\modules\` — read all of them

### Source material (for context and comparison)
3. Autoboard repo at `C:\Code\autoboard` — key files:
   - `README.md`, `CLAUDE.md`
   - `skills/session-workflow/SKILL.md`, `skills/run/SKILL.md`, `skills/brainstorm/SKILL.md`
   - `skills/task-manifest/SKILL.md`, `skills/session-spawn/SKILL.md`
   - `skills/receiving-review/SKILL.md`, `skills/coherence-audit/SKILL.md`, `skills/audit/SKILL.md`
   - `skills/merge/SKILL.md`, `skills/knowledge/SKILL.md`, `skills/failure/SKILL.md`
   - `agents/plan-reviewer.md`, `agents/code-reviewer.md`
4. Taskmill at `C:\Code\millhouse\plugins\taskmill\` — key files:
   - `skills/mill-discuss/SKILL.md`, `skills/mill-finalize/SKILL.md`, `skills/mill-do/SKILL.md`
   - `skills/mill-commit/SKILL.md`, `skills/mill-formats/SKILL.md`
   - `doc/skill-scripts.md`
5. Motlin repo at `C:\Code\motlin-claude-code-plugins` — skim for plugin conventions
6. Codeguide at `C:\Code\millhouse\plugins\codeguide\` — read all skills in `skills/*/SKILL.md`
7. Testing skill at `C:\Code\millhouse\plugins\code\skills\testing\SKILL.md` — recently updated with coverage, TDD discipline, and test quality rules

## Key Design Decisions (verify consistency across all docs)

- **GitHub Projects V2 is the only backlog.** No local backlog files.
- **No Python scripts.** CC reads/writes files directly.
- **Worktree spawning is always user-initiated** (`helm-start -w`). CC never auto-spawns.
- **Plans are locked after approval** (`approved: true` in frontmatter).
- **Merge uses checkpoint branches** for rollback safety.
- **Merge uses lock files** (`_helm/scratch/merge.lock`) for concurrent merge safety.
- **Failure classification** with 4 categories before retrying.
- **Branch naming** follows `{prefix}/{parent-slug}/{slug}` template from `_helm/config.yaml`.
- **Knowledge files** live in tracked `_helm/knowledge/`.
- **Ephemeral files** live in gitignored `_helm/scratch/` (plans, briefs, reviews, status, merge lock).
- **Coherence audits** run during `helm-merge`, not per-task.
- **Testing rules** defined in `@code:testing` (general) and language-specific skills. Helm's code-reviewer enforces them with specific BLOCKING triggers.
- **Role descriptions** on each skill and agent (collaborative designer, session agent, integration engineer, independent reviewer).
- **helm-start discussion** is structured: explore codebase first, one question at a time, multiple choice where possible, 2-3 approaches with trade-offs, incremental plan presentation.

## Review Criteria

### Completeness
- Every skill: clear entry point, exit condition, error handling?
- What happens when things go wrong? (merge conflict, reviewer disagrees, test keeps failing, worktree spawns from worktree spawned from worktree)
- Are all design decisions consistently applied across all doc files? (check for stale references to `.llm/`, old `_helm/status.md` paths, missing `scratch/` prefixes)

### Feasibility
- Can CC actually do everything described? (open VS Code, create worktrees from worktrees, read GitHub Projects board, send Slack notifications)
- Are there Claude Code platform constraints that block something?
- Is the notification system realistic?

### Consistency
- Do cross-references between doc files align? (Does skills.md's helm-go flow match what plans.md describes? Does merge.md's flow match what skills.md says?)
- Is the kanban column set consistent between kanban.md and skills.md?
- Is `_helm/` directory structure consistent across all docs? (tracked: `knowledge/`, `changelog.md`, `config.yaml`; ignored: `scratch/`)
- Do the testing requirements in reviews.md align with what `code:testing` defines?

### Gaps vs Source Material
- What does Autoboard handle that Helm doesn't address?
- What does Taskmill do today that Helm would lose?
- Is the receiving-review protocol complete enough to implement, or just referenced?
- Is the codeguide integration accurate to how the codeguide skills actually work?
- Does Helm's TDD enforcement match Autoboard's rigor? (Autoboard: skipping RED verification is a BLOCKING violation)

### Over-engineering
- Is anything more complex than needed?
- Can any skills be simplified or merged?
- Are there Autoboard patterns included that don't make sense without Autoboard's parallelism?

### New Concerns
- GitHub Projects V2 as sole backlog — failure modes? Rate limits? Latency? Board gets out of sync?
- No Python scripts — what prevents CC from corrupting tracked files (`_helm/knowledge/`, `_helm/changelog.md`)?
- Branch naming with deep nesting — practical limits of `hanf/main/auth/oauth/token-refresh`?
- `helm-start` discussion principles — are they specific enough to produce consistent behavior, or too vague?
- Testing enforcement — is the code-reviewer's BLOCKING list sufficient, or will CC find ways to write tests that technically pass these checks but are still shallow?

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
What's well-designed. Brief list.

### Recommendations
Ordered list of what to fix first, with reasoning.

Write your review to `C:\Code\millhouse\plugins\helm\doc\reviews\review-02-result.md`.
