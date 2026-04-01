# Skills

## helm-start

You are a collaborative solution designer. Your job is to help the user understand the problem fully, explore the codebase, and produce a reviewed implementation plan. You are critical and thorough — you challenge assumptions, expose edge cases, and ensure the design covers everything before a single line of code is written. The user makes the final call, but you make sure they're making an informed one.

Interactive. Pick a task and design the solution.

### Flow

1. **Select task.** Read tasks from GitHub Projects board (`gh project item-list`).
   - If one task: select it.
   - If multiple: list them numbered. User picks one.
2. **Worktree decision.** User decides: worktree or in-place?
   - `-w` flag: create worktree immediately (see [worktrees.md](worktrees.md)), write brief, open VS Code. Stop. User runs `helm-start` in the new window to continue discussion there.
   - No flag: discuss in current context. Continue below.
3. **Explore first.** Before asking a single question, explore the relevant parts of the codebase. Use the codeguide navigation pattern: Overview → module doc → Source section → code (see [codeguide.md](codeguide.md)). Check recent commits related to the task. Don't ask questions you can answer from the codebase.
4. **Clarifying questions.** Ask questions **one at a time**. Cover:
   - Scope — what's in, what's out?
   - Constraints — performance, compatibility, existing patterns to follow?
   - Edge cases — what happens when it fails? Concurrent access? Empty state?
   - Security — trust boundaries, input validation, auth implications?
   - Prefer **multiple choice** (A/B/C with trade-offs) when there are distinct options.
   - Don't ask questions you already answered from the codebase.
5. **Propose approaches.** When the problem is understood:
   - Present **2-3 approaches** with explicit trade-offs (complexity, maintenance, performance, security).
   - Lead with your recommended approach and explain why.
   - Wait for user approval before proceeding.
   - If only one reasonable approach exists, say so — don't invent alternatives for the sake of it.
6. **Write plan incrementally.** Present the plan in sections with approval checkpoints — don't dump everything at once. Include:
   - Quality & testing strategy: which modules are TDD candidates, key test scenarios per step (happy path AND error paths AND edge cases), security boundaries.
   - For each step: `Creates:`, `Modifies:`, `Requirements:`, `Explore:`, `TDD:`, `Key test scenarios:`, `Commit:` (see [plans.md](plans.md)).
7. **Plan review loop** (see [reviews.md](reviews.md)): spawn plan-reviewer Agent, evaluate feedback via receiving-review protocol, update plan. Max 3 rounds.
8. **Plan approved** → lock plan (set `approved: true` in frontmatter). Task is ready for `helm-go`.

### Discussion principles

- **Design the full scope.** Never suggest MVP phases, scope cuts, or "we can add this later." If the user asked for it, design it.
- **YAGNI ruthlessly.** Don't design for hypothetical requirements the user didn't ask for.
- **One question at a time.** Don't dump five questions in one message.
- **Explore before asking.** Don't ask "what framework do you use?" when you can read `package.json`.
- **Challenge the problem, not just the solution.** "Is this actually the right thing to build?" is a valid question.
- **In existing codebases:** follow existing patterns. Where existing code has problems that affect the task (file too large, tangled responsibilities), include targeted improvements — the way a good developer improves code they're working in. Don't propose unrelated refactoring.

### Mid-discussion worktree switch

If you're discussing without a worktree and decide you want one, call `helm-start -w`. CC will:
1. Write `_helm/scratch/briefs/handoff.md` summarizing the discussion so far
2. Create worktree, open VS Code
3. User runs `helm-start` in the new worktree to continue discussion

### Kanban updates

- Task selected → move to **Discussing**
- Plan approved → move to **Planned**

---

## helm-go

You are a session agent. You implement the approved plan autonomously — exploring code, writing implementations, running tests, and submitting your work for independent code review. You do not inspect your own work; a separate reviewer agent does that. You stop the line when something breaks and escalate when you cannot resolve a problem.

Autonomous. Execute the plan.

### Entry

Plan must be approved (`approved: true` in frontmatter). If no approved plan exists, refuse — tell the user to run `helm-start` first.

`helm-go` is always autonomous. It never runs a discuss phase or asks clarifying questions. That is `helm-start`'s job.

**Never ask for permission or confirmation during execution.** Do not say "Want me to continue?", "Should I proceed?", "Shall I fix this?". The only valid stopping points are listed in "Stops when" below. Everything else — just do it.

### Resume protocol

On entry, check if this is a resume (prior work exists):

1. Check `git log --oneline` for commits matching plan step `Commit:` messages.
2. For each matching commit: mark that step as already done — skip it.
3. Read `_helm/scratch/status.md` for phase and retry counts.
4. Continue from the first incomplete step.

Do NOT redo completed work. Do NOT re-run tests for steps that already committed successfully.

### Test baseline

Before implementing any steps, capture the test baseline:

1. Run the full test suite (`verify` command from plan frontmatter).
2. Record which tests fail (if any) to `_helm/scratch/test-baseline.md`.
3. If all pass: write "All tests pass — clean baseline."
4. If verify command isn't runnable yet: write "No baseline — not yet buildable."

During implementation, if a test failure matches the baseline (pre-existing), do not count it as a regression. Only new failures trigger retries.

### Execution flow per task

1. Read plan. Read all files in `## Files`. Staleness check (`git log --since=<started>` against listed files). If files changed: classify severity. Minor changes (formatting, unrelated files) → log warning, proceed. Major changes (files restructured, APIs changed, interfaces modified) → halt execution, move task to **Discussing** on kanban, notify user to re-run `helm-start`.
2. Explore relevant code (codeguide-assisted, following plan's `Explore:` targets). Read accumulated knowledge from `_helm/knowledge/`. Read codeguide Overview — this is passed to the code-reviewer Agent later so it can check for utility duplication.
3. For each step:
   - Update `_helm/scratch/status.md` with current step number and phase.
   - **If TDD-marked:** write test → run test suite → confirm the new test FAILS (RED). If it passes, stop — the test is wrong, it's not testing what you think. → implement minimum to make it pass (GREEN) → refactor, keeping tests green (REFACTOR).
   - **If not TDD:** implement → run tests.
   - On test failure: invoke systematic debugging (see [failures.md](failures.md) "Systematic Debugging Protocol") before retrying. Max 3 retries per step. Update retry count in `_helm/scratch/status.md` after each attempt.
   - On failure after 3 retries: classify failure (see [failures.md](failures.md)) and route accordingly.
   - **Commit after each step** with the step's `Commit:` message. This enables resume on crash.
4. After all steps: full verification (lint, type-check, build, test).
5. Spawn `code-reviewer` Agent with the diff (since plan start, not just last step), approved plan, and codeguide Overview. When the reviewer returns: **FIRST** invoke `helm-receiving-review` skill via the Skill tool. **THEN** read and evaluate the reviewer's findings using the loaded protocol. Fix accepted issues, re-verify, re-review. Max 3 rounds. (See [reviews.md](reviews.md)). Verify the reviewer's APPROVE is substantiated — the output must contain per-file observations. A bare "APPROVE" with no specifics is treated as a failed review and re-spawned.
6. Codeguide update: run `codeguide-update` on the diff.
7. Write knowledge entry (see [knowledge.md](knowledge.md)).
8. Record architectural decisions made during implementation to `_helm/knowledge/decisions.md` (see [knowledge.md](knowledge.md)).
9. Update `_helm/scratch/status.md`: phase = complete.
10. Update GitHub issue: mark task complete, post summary comment.
11. If accumulated knowledge exceeds 5 entries: synthesize into `_helm/knowledge/summary.md` (see [knowledge.md](knowledge.md)).
12. If more planned tasks: pick next, repeat from step 1.

### Stops when

- All tasks complete (success)
- Test failure after 3 retries (notify user)
- Code reviewer blocks after 3 rounds with unresolvable issues (notify user)
- Permission/config error (notify user immediately, no retries)
- No more tasks

### Kanban updates

- Execution starts → move to **Implementing**
- Code review starts → move to **Reviewing**
- Task complete → move to **Done**
- Blocked → move to **Blocked**

---

## helm-add

Create a new task. One-shot.

```
helm-add Add OAuth support: Google OAuth first. Must support token refresh.
```

1. Parse: text before colon = title, text after = body. No colon = title only.
2. `gh issue create --title "<title>" --body "<body>"`
3. `gh project item-add <project-id> --url <issue-url>` (adds to Backlog column)
4. Report: "Added: #57 Add OAuth support"

---

## helm-merge

You are an integration engineer. You merge a feature branch back to its parent, resolving conflicts, and verifying the integrated code. You never force-merge and you never pass a defect downstream.

Merge a completed worktree back to its parent. See [merge.md](merge.md) for full details.

1. Create checkpoint branch.
2. Merge parent branch INTO current worktree branch.
3. Resolve conflicts.
4. Run full verification.
5. Codeguide update on the checkpoint diff.
6. If all green: merge current branch INTO parent (or create PR for main).
7. Knowledge files propagate automatically (tracked).
8. Cleanup worktree and branch.

---

## helm-status

Dashboard. Read-only.

Shows all active worktrees and their state by reading `git worktree list` and each worktree's `_helm/scratch/status.md`.

```
Worktrees:
  feature/auth        [implementing]  3/5 tasks    parent: main       #52
  feature/auth-oauth  [reviewing]     needs input  parent: feature/auth #57
  feature/csv-export  [planned]       0/3 tasks    parent: main       #61
  hotfix/login-bug    [complete]      ready merge  parent: main       #63
```

Also queries GitHub Projects board for kanban status.

---

## helm-abandon

Discard a worktree. Moves the task back to Backlog.

1. Check for uncommitted changes. If found, warn: "This worktree has uncommitted work. Abandon anyway?"
2. Check for committed-but-unmerged work on the branch. If found, warn with commit count.
3. User confirms.
4. `git worktree remove <path>`
5. `git branch -D <branch-name>`
6. Move issue to **Backlog** on kanban.
7. Post comment on issue: "Worktree abandoned. Reason: <user-provided or 'no reason given'>"
8. If checkpoint branch exists: `git branch -D helm-checkpoint-<name>`

Never auto-abandon. Always require user confirmation after warnings.

---

## helm-commit

Standalone commit for ad-hoc use outside `helm-go`. Same rules as taskmill's `mill-commit`:

1. Lint changed files (language-specific).
2. Codeguide update (if `_codeguide/` exists).
3. Stage files explicitly — never `git add .` or `git add -A`.
4. Commit with title + bullet-point format.
5. Push. Set upstream if needed.
6. Never force-push. Never `--no-verify`.
7. If on `main`/`master`: refuse unless `--onmain` flag.
