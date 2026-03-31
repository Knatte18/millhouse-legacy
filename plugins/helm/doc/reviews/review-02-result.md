# Helm Design Review — Round 2 Result

---

## Blocking Issues

### 1. helm-go has two conflicting modes

**What:** helm-go is described as "Autonomous. Execute the plan." but entry path 1 (fresh worktree with brief) makes it interactive — it runs a discuss phase with the user, writes a plan, and does plan review before implementing.

**Where:** skills.md, helm-go "Entry paths" section vs. overview.md execution model table and helm-go role description.

**Why:** This is a fundamental role confusion. The overview says "The user controls the transition" between interactive and autonomous, but in the worktree-with-brief flow, helm-go silently becomes interactive. The role description ("You are a session agent... You implement the approved plan autonomously") contradicts the actual flow. Code review agents receive context saying the implementer is autonomous — but it isn't always.

**Suggestion:** Split the flows. Option A: `helm-start -w` opens VS Code, and the user runs `helm-start` (not `helm-go`) in the new window — discussion continues interactively, then the user explicitly calls `helm-go` after plan approval. Option B: keep the brief path in helm-go, but clearly document it as a "bootstrap phase" that transitions to autonomous mode after plan approval, and update the role description to reflect both phases.

### 2. Merge lock file is inaccessible across sibling worktrees

**What:** merge.md places the lock at `_helm/scratch/merge.lock` in the parent worktree, but the mechanism for locating the parent's filesystem path is unspecified.

**Where:** merge.md "Merge Locking" section.

**Why:** Two sibling worktrees merging to the same parent need to read/write the same lock file. The status file records `parent: feature/auth` (a branch name), not a path. Resolving branch to filesystem path requires `git worktree list` + parsing, and this is a critical concurrency path — if it fails, two simultaneous merges corrupt the parent branch.

**Suggestion:** Specify the full lock-acquisition flow: (1) `git worktree list --porcelain` to resolve parent branch to path, (2) write lock with PID/timestamp to `<parent-path>/_helm/scratch/merge.lock`, (3) handle the case where parent is the repo root (which may not have `_helm/scratch/`). Consider using git's built-in lock mechanisms instead.

### 3. Codeguide update happens after commit in helm-go

**What:** skills.md helm-go step 6 commits, then step 9 runs codeguide-update. But codeguide-update modifies docs that should be part of the commit.

**Where:** skills.md helm-go flow (steps 6 and 9) contradicts codeguide.md "helm-go (after implementation, before commit)" section.

**Why:** If codeguide-update runs after commit, the doc changes are uncommitted artifacts. They'll either be included in the next task's commit (wrong scope) or lost.

**Suggestion:** Move codeguide-update before the commit step in helm-go's flow. Align skills.md with codeguide.md's stated ordering: implement → codeguide-update → commit.

### 4. No format-protection mechanism for tracked files

**What:** Helm drops Python scripts ("CC reads/writes files directly") but provides no alternative protection for tracked files (`_helm/knowledge/`, `_helm/changelog.md`, `_helm/config.yaml`).

**Where:** open-questions.md "Python scripts" resolved decision.

**Why:** Taskmill uses scripts specifically to prevent CC from corrupting tracked files — CC gets only the relevant extract and never writes the full file directly. Without scripts, a single malformed write to `_helm/config.yaml` (which stores GitHub Projects IDs) could break all kanban operations. Knowledge files and changelog are lower risk but still tracked and shared across worktrees via merge.

**Suggestion:** Either: (A) Keep the "no scripts" decision but add explicit format specs with validation hooks (a pre-commit hook that checks `_helm/` file formats). Or (B) bring back lightweight scripts for the highest-risk files (config.yaml, changelog.md) where a bad write has cascading effects.

---

## Important Gaps

### 1. No helm-setup skill

**What:** kanban.md references setup steps (create project, configure columns, store IDs), and open-questions.md acknowledges the need, but no skill is defined.

**Where:** kanban.md "Setup" section, open-questions.md "First-run experience."

**Why:** Without it, first-time users must manually execute GraphQL mutations to configure the GitHub Projects board, discover field IDs and option IDs, and populate `_helm/config.yaml`. This is the single biggest adoption barrier.

**Suggestion:** Define `helm-setup` as a skill with clear steps: check `gh auth status`, create or link project, configure Status field columns, discover and cache all IDs in `_helm/config.yaml`, add `_helm/scratch/` to `.gitignore`, create directory structure.

### 2. Handoff brief format is unspecified

**What:** When `helm-start -w` creates a worktree, it writes `_helm/scratch/briefs/handoff.md` but the brief's structure is not defined.

**Where:** skills.md "helm-start" flow step 2 / worktrees.md "Creation" step 4.

**Why:** Autoboard's session-spawn skill has a detailed brief format (identity, task records, knowledge, config, skills, tracking, resume detection). Without a defined format, the handoff brief will vary in quality and completeness, and the receiving helm-go has no reliable structure to parse.

**Suggestion:** Define the brief format in plans.md or a new briefs.md: task title and issue number, discussion summary, key decisions so far, knowledge from parent worktree, relevant codeguide modules, config (verify command, dev-server), parent branch and worktree path.

### 3. GitHub Projects API ID discovery is unspecified

**What:** kanban.md uses `--field-id` and `--single-select-option-id` flags but doesn't specify how these IDs are discovered.

**Where:** kanban.md "Updating status" section.

**Why:** These are GraphQL node IDs that must be queried via `gh api graphql`. Without specifying the discovery queries, every implementation of helm will need to reverse-engineer the GitHub Projects V2 GraphQL schema.

**Suggestion:** Add a "Discovery" section to kanban.md with the exact `gh api graphql` queries needed to resolve project ID, field IDs, and option IDs. These should be run during `helm-setup` and cached in `_helm/config.yaml`.

### 4. Receiving-review skill invocation is implicit

**What:** Autoboard mandates "invoke `/autoboard:receiving-review` skill BEFORE responding to reviewer suggestions" as the literal first action. Helm's flow just says "evaluate feedback via receiving-review protocol" without explicitly requiring skill invocation.

**Where:** skills.md helm-go step 5, reviews.md "Receiving-Review Protocol" section.

**Why:** The protocol's value depends on it being loaded into context BEFORE the agent sees review findings. If the agent reads findings first, it's already forming rationalizations. Autoboard learned this the hard way — the skill loading is a forcing function.

**Suggestion:** Add explicit instruction to helm-go and the code reviewer interaction: "FIRST ACTION: invoke `helm-receiving-review` skill. Then read reviewer findings. Do not read findings before invoking the skill."

### 5. TDD RED verification is under-enforced

**What:** Helm's code reviewer checks "TDD-marked steps where diff shows implementation committed without a preceding failing test" but this is nearly impossible to verify from a diff alone.

**Where:** reviews.md code reviewer definition.

**Why:** Autoboard enforces RED verification during execution (session-workflow step 4: "write test → verify it fails") AND at review time. Helm's helm-go flow says "write test → verify it fails (RED)" but the code reviewer's check is weak — a diff doesn't show test execution order. The real enforcement must happen during implementation, with explicit "run test, confirm failure" steps.

**Suggestion:** Add to helm-go flow: "After writing the test (RED phase), run the test suite. If the new test PASSES, stop — the test is wrong. Do not proceed to GREEN until the test fails." This makes RED verification an implementation-time gate, not just a review-time aspiration.

### 6. Retry count tracking mechanism missing

**What:** failures.md specifies retry budgets (3 per step, 3 per review round, 3 per audit cycle) but doesn't specify how the count is persisted.

**Where:** failures.md "Retry Budget" section.

**Why:** Without tracking, CC may retry indefinitely or reset the counter when context compresses. Autoboard tracks retries via session status files.

**Suggestion:** Track retry counts in `_helm/scratch/status.md` (e.g., `step_3_retries: 2`, `review_round: 1`). Update after each attempt.

### 7. Dimension template loading during execution is unspecified

**What:** coherence.md says quality dimensions exist and reviews check them, but the mechanism for loading dimension templates during helm-go execution is not specified.

**Where:** coherence.md "Quality Dimensions" section.

**Why:** The plan includes `## Quality dimensions: security, api-design, test-quality` but there's no step in helm-go that says "load dimension templates for active dimensions and apply them during implementation." The code reviewer receives "active quality dimensions" but where from?

**Suggestion:** Add to helm-go flow: "Read `## Quality dimensions` from plan. Load dimension templates from `_helm/dimensions/` (or plugin defaults). Pass dimension criteria to code-reviewer Agent prompt."

---

## Minor Issues

1. **Stale cross-reference:** overview.md document index lists `modules/review-prompt.md` — this is the review prompt itself, not a design module. Remove or rename.

2. **open-questions.md has resolved items in "Still Open":** "Worktree naming convention" and "_helm/ directory structure" both have `**Decision:**` headers with final answers. Move them to Resolved.

3. **Windows-only notification fallback:** notifications.md mentions BurntToast (PowerShell). No macOS/Linux equivalent. Add `osascript` for macOS and `notify-send` for Linux, or mark as Windows-only.

4. **helm-commit duplicates mill-commit:** skills.md redefines all mill-commit rules inline while also saying "Same rules as taskmill's mill-commit." Either reference the skill or fully specify — not both.

5. **Dimension config vs auto-detection priority unclear:** coherence.md describes both explicit config (`.claude/dimensions.json` with `"active"` list) and auto-detection (based on diff content). Which takes priority? Are auto-detected dimensions added to the configured list, or does the config override auto-detection?

6. **Knowledge synthesis trigger not in flow:** knowledge.md says synthesis happens "when accumulated knowledge exceeds ~5 entries" but helm-go's per-task flow doesn't include a synthesis step. Add it between tasks.

7. **`hanf/main` working base convention:** worktrees.md implies the user never works on `main` directly — always through a `{prefix}/main` worktree. This is a strong convention not explicitly stated or explained.

8. **Slack MCP server feasibility:** notifications.md says "Implementation: Slack MCP server or incoming webhook." Incoming webhooks are simple. An MCP server for Slack is significant scope. Recommend webhooks as the default and MCP as optional.

9. **Plan storage comment on GitHub issue:** plans.md says "The GitHub issue for the task links to the plan via a comment posted by helm-start after approval." But plans are in gitignored `_helm/scratch/`. The comment would contain a local filesystem path — useless to anyone else and stale after worktree cleanup.

---

## Strengths

1. **Clean phase separation.** Interactive design (helm-start) and autonomous execution (helm-go) with user-controlled transition is the right model for human-in-the-loop AI development.

2. **Receiving-review protocol.** Adopting Autoboard's "fix everything, the only valid escape is proven harm" principle with the forbidden-dismissals list prevents CC's natural tendency to rationalize away review findings.

3. **Checkpoint branches for merge rollback.** Simple, reliable, uses native git. No complex undo machinery.

4. **Knowledge curation with synthesis.** Prevents context bloat across tasks while preserving cross-task learning. The synthesis threshold (~5 entries) is practical.

5. **Codeguide integration mapping.** Each helm phase has a clear, specific codeguide touchpoint. The "don't use maintain during normal flow, only update" distinction is correct.

6. **Per-step plan structure.** Explore targets, TDD marking, key test scenarios per step gives code reviewers specific verification criteria rather than vague "check the tests."

7. **GitHub Projects as single source of truth.** Eliminates the dual-source-of-truth problem of local backlog files + external trackers. Team visibility without terminal access.

8. **Worktree model leverages git natively.** No custom parallelism machinery — just git worktrees with separate VS Code windows. The constraint (one thread per worktree) is honest about CC's sequential nature.

9. **Failure classification before retry.** Four categories with distinct response strategies prevents wasted retries on config errors and dependency blocks.

10. **Quality dimensions as selective overlays.** Loaded per-diff on top of always-on skills. Avoids the overhead of checking all 13 dimensions on every change.

---

## Recommendations

Ordered by priority:

1. **Fix helm-go's dual-mode confusion (Blocking #1).** This affects the core architecture. Decide whether helm-go is always autonomous or has a bootstrap mode, and make all docs consistent with that decision. Recommendation: keep helm-go autonomous-only, have `helm-start -w` tell the user to run `helm-start` (not `helm-go`) in the new window.

2. **Define helm-setup (Gap #1) and GitHub API discovery (Gap #3).** Without these, nobody can use Helm. They're the first thing a new user hits.

3. **Fix codeguide update ordering (Blocking #3).** Small fix, high impact — wrong ordering means docs drift from code after every task.

4. **Specify merge lock resolution (Blocking #2).** Under-specified concurrency paths are silent data-loss risks.

5. **Add format protection for tracked files (Blocking #4).** Decide on hooks or scripts. The "no scripts" decision is fine for gitignored files but risky for tracked `_helm/config.yaml`.

6. **Define handoff brief format (Gap #2).** Required for the worktree flow to work reliably.

7. **Make receiving-review invocation explicit (Gap #4) and TDD RED enforcement implementation-time (Gap #5).** These are the quality enforcement mechanisms that distinguish Helm from a naive automation. If they're vague, CC will skip them.

8. **Clean up minor issues.** Move resolved open questions, fix stale cross-references, clarify dimension config priority.
