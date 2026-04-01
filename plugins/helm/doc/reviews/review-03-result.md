# Helm Design Review — Round 3 Result

---

## Blocking Issues

### 1. reviews.md still references "fresh worktree path" plan review in helm-go

**What:** reviews.md line 14 says "Plan review in `helm-go` (fresh worktree path): same flow, but the discuss phase with the user happens first." This contradicts the round 2 fix that helm-go is always autonomous and never runs a discuss phase.

**Where:** reviews.md "Plan Review" section, paragraph after step 8.

**Why:** Round 2 blocking issue #1 resolved that helm-go is always autonomous. skills.md and open-questions.md are consistent with this decision. But reviews.md still describes a hybrid flow where helm-go does discussion. An implementer reading reviews.md will be confused about whether helm-go can be interactive.

**Suggestion:** Remove or rewrite reviews.md line 14. It should say something like: "Plan review happens exclusively during `helm-start`. `helm-go` requires an already-approved plan."

### 2. helm-go step numbering/ordering inconsistency with code review

**What:** skills.md helm-go step 6 says "MANDATORY: Invoke `helm-receiving-review` skill BEFORE reading reviewer findings. Then spawn `code-reviewer` Agent..." But the receiving-review protocol is meant to be loaded before *reading findings*, not before *spawning the reviewer*. The actual sequence should be: spawn reviewer → invoke receiving-review → read findings. Currently, the text conflates spawning and reading.

**Where:** skills.md helm-go step 6.

**Why:** If CC interprets this literally, it will: (1) invoke receiving-review, (2) spawn code-reviewer, (3) read findings. Steps 1 and 2 are reversed from intent. The receiving-review skill should be loaded *after* the reviewer finishes but *before* the agent reads the reviewer's output. Autoboard's session-workflow is explicit about this: "invoke receiving-review skill first" means first action *when processing results*, not first action before spawning.

**Suggestion:** Rewrite step 6: "Spawn `code-reviewer` Agent with the diff, approved plan, and active quality dimensions. When the reviewer returns: FIRST invoke `helm-receiving-review` skill via the Skill tool. THEN read and evaluate the reviewer's findings using the loaded protocol."

### 3. `_helm/scratch/reviews/` referenced in open-questions.md but never used anywhere

**What:** open-questions.md "_helm/ directory structure" decision lists `scratch/reviews/` as a directory, but no skill or flow writes review results there. Code review is agent-to-agent (results returned directly). Plan review results are also inline.

**Where:** open-questions.md directory structure diagram.

**Why:** An implementer will create this directory in helm-setup and wonder what populates it. If it's intended for storing review results (like Taskmill's `.llm/reviews/`), no skill writes there. If it's vestigial, it adds confusion.

**Suggestion:** Either (A) define what goes in `scratch/reviews/` (e.g., code-reviewer and plan-reviewer findings stored for audit trail) and add write steps to the relevant flows, or (B) remove it from the directory structure.

---

## Important Gaps

### 1. No "just do it" principle — helm-go lacks explicit no-permission-asking rule

**What:** Autoboard's `run` skill has an explicit rule: "Do NOT ask 'Want me to continue?'" with a table of anti-patterns. Helm's helm-go says "autonomous" but never explicitly forbids asking for permission during execution.

**Where:** skills.md helm-go role description and flow.

**Why:** CC's default behavior is to ask for confirmation, especially after errors or when context compresses. Without an explicit prohibition, helm-go will ask "Should I continue to the next step?" or "Want me to fix this?" during autonomous execution, breaking the flow. Autoboard learned this is a real failure mode.

**Suggestion:** Add to helm-go's role description: "Never ask for permission or confirmation during execution. Do not say 'Want me to continue?' or 'Should I proceed?' The only valid stopping points are: exhausted retries, permission/config errors, and unresolvable review disputes. Everything else, just do it."

### 2. No plan step granularity enforcement

**What:** Taskmill enforces "one file per step" in plans. Helm's plan format has `Creates:` and `Modifies:` per step but no rule about scope limits. A plan step could touch 10 files, making code review nearly impossible.

**Where:** plans.md per-step fields.

**Why:** The code reviewer evaluates per-step. If a step is "refactor the entire auth module" touching 15 files, the reviewer can't meaningfully evaluate it. Taskmill's constraint forces decomposition. Autoboard's plan reviewer explicitly checks for oversized steps.

**Suggestion:** Add a guideline to plans.md: "Each step should touch a small, reviewable scope. Prefer one file created or modified per step. If a step must touch multiple files, each file change should serve a single coherent purpose. The plan reviewer should flag steps that are too broad."

### 3. helm-merge codeguide-update scope may be wrong

**What:** codeguide.md says helm-merge runs `codeguide-update` on "diff between parent HEAD and merged worktree HEAD." But after step 5 (merge worktree into parent), the parent HEAD *is* the worktree HEAD. The diff would be empty.

**Where:** codeguide.md "helm-merge (after merge)" section, and merge.md step 7.

**Why:** The codeguide-update must run *before* the final merge to parent, when the diff is still meaningful. After the merge, parent and worktree are the same. Or it should reference the checkpoint branch to compute the diff.

**Suggestion:** Clarify the scope: "Run `codeguide-update` with scope `git diff helm-checkpoint-<name>..HEAD` — this captures all changes introduced by the worktree, including conflict resolutions." And place it in merge.md between steps 4 (coherence audit) and 5 (merge to parent).

### 4. No mechanism for plan revision during helm-go

**What:** helm-go's staleness check (step 1) detects changed files and says "notify user that the plan may need revision." But then what? The plan is locked (`approved: true`). There's no defined path for: halt execution, return to helm-start for revision, re-approve.

**Where:** skills.md helm-go step 1, plans.md "Plan Locking" and "Staleness Detection."

**Why:** If files changed significantly since the plan was written (e.g., another worktree merged to the same parent), the plan may be fundamentally wrong. "Notify user" is insufficient — the flow needs a defined state transition: either (A) halt and tell user to re-run helm-start with a new plan, or (B) allow helm-go to propose minor revisions without full re-planning.

**Suggestion:** Define the staleness response: "If staleness is detected: (1) classify severity — minor (formatting, unrelated changes) vs. major (files restructured, APIs changed). (2) Minor: log warning, proceed. (3) Major: halt execution, move task back to Discussing on kanban, notify user to re-run `helm-start`."

### 5. Missing explicit test for `helm-start -w` brief when no discussion has happened

**What:** worktrees.md step 4 says "Write `_helm/scratch/briefs/handoff.md` (context from parent discussion, if any)." But what does the brief contain if `helm-start -w` is called immediately with no prior discussion?

**Where:** worktrees.md "Creation" step 4, plans.md "Handoff Brief Format."

**Why:** The handoff brief format in plans.md has "Discussion Summary" that says "If no discussion happened, just the task description from the GitHub issue body." This is good, but it's buried. The worktrees.md flow should reference this explicitly so implementers don't skip writing the brief when there's no discussion.

**Suggestion:** Small fix: in worktrees.md step 4, change to: "Write `_helm/scratch/briefs/handoff.md` (see [plans.md](plans.md) Handoff Brief Format). If no discussion has happened, populate Discussion Summary from the GitHub issue body."

### 6. Autoboard's "fabrication detection" pattern not adopted

**What:** Autoboard has explicit patterns for detecting when agents fabricate results (e.g., QA agents claiming infrastructure failure when actually stuck). Helm's review and audit flows trust agent outputs at face value.

**Where:** Not present in Helm docs. Relevant Autoboard context: run skill QA gate processing.

**Why:** This is a real failure mode. Code reviewers can claim "APPROVE" without actually reviewing. Coherence audit agents can report "no findings" when they ran into context limits. Autoboard addresses this by validating claims against evidence. For Helm's simpler model (no QA gate), the risk is lower but still present in code review and coherence audit.

**Suggestion:** Add a lightweight validation step after code review: "Verify the reviewer's APPROVE is substantiated — the review output must contain per-file observations. A bare 'APPROVE' with no specifics is treated as a failed review and re-spawned." Similar for coherence audit.

---

## Minor Issues

1. **kanban.md step 5 GraphQL query assumes `user` owner.** The query uses `user(login: "<owner>")` but org repos need `organization(login: "<owner>")`. The note says "For org-owned repos, use `organization`" — but helm-setup should detect this automatically (check if owner is a user or org via `gh api users/<owner>` and inspect the `type` field).

2. **`_helm/changelog.md` is tracked but never written to.** open-questions.md lists it as "Still Open" (carry over Taskmill's format?), but the directory structure in the same file lists it as a tracked file. If it's undecided, remove it from the directory structure until decided.

3. **Retry count tracking placement.** skills.md helm-go step 11 says "Update retry counts in `_helm/scratch/status.md`" *after* codeguide-update and commit (steps 7-8). But retry counts should be updated *during* step 4 (per-step retries) and step 6 (review round retries), not at the end. Current placement means a crash before step 11 loses retry state.

4. **`helm-commit` says "Same rules as taskmill's `mill-commit`" then re-specifies them all.** Round 2 flagged this (minor #4). Still the same. Either reference the skill or fully specify — not both.

5. **Worktree path-template `"../{slug}"` creates siblings at repo root level.** If the repo is at `C:\Code\myproject`, worktrees land at `C:\Code\auth`, `C:\Code\csv-export`. This may surprise users expecting them under the repo. The config is correct but the implication should be documented: "Worktrees are created as sibling directories, not inside the repo."

6. **No `helm-abandon` or worktree-discard flow.** Review prompt's "What's missing?" asks about abandoning a worktree. Currently no defined flow — user must manually `git worktree remove` and clean up. Should at minimum be documented as a manual procedure, even if not a full skill.

7. **notifications.md config at `~/.claude/helm.json` is outside `_helm/`.** All other Helm config is in `_helm/config.yaml`. Having notification config in a different location (`~/.claude/`) is justified (global, not per-repo) but the relationship should be cross-referenced in both files.

8. **`helm-start` step 3 "Explore first" doesn't specify codeguide navigation pattern.** codeguide.md defines a specific 3-step pattern (Overview → module doc → Source). helm-start step 3 says "explore the relevant parts of the codebase (codeguide-assisted)" but doesn't reference the pattern. Cross-reference it.

9. **merge.md conflict resolution says "accept worktree version" for generated files.** This is wrong for lock files (`package-lock.json`, `yarn.lock`) — these should be regenerated by running the install command, not accepted from either side.

10. **Dimension config `.claude/dimensions.json` placement.** This is inside the `.claude/` directory which is for Claude Code user settings. Per-repo quality config belongs in `_helm/` or project root, not `.claude/`.

---

## Strengths

1. **All round 2 blocking issues are resolved.** helm-go is cleanly autonomous, merge lock is fully specified with `git worktree list --porcelain`, codeguide-update is before commit, and helm-setup has exact GraphQL queries.

2. **Handoff brief format is well-designed.** The structure (issue, parent, discussion summary, knowledge, codeguide modules, config) covers everything the receiving `helm-start` needs without over-constraining it. The "brief informs but does not constrain" principle is good.

3. **helm-setup is thorough.** 9 steps with exact commands, GraphQL mutations, config file template, and user-friendly report. This went from "important gap" to one of the strongest sections.

4. **Dimension config vs. auto-detection is cleanly resolved.** "Config sets the pool, auto-detection picks from it" is a clear separation that avoids both config overhead and magic.

5. **Plan storage on GitHub issue (content, not path) fixes the round 2 concern.** plans.md now explicitly says "Not a file path — the actual content, since plan files are gitignored and won't survive worktree cleanup."

6. **Cross-platform notifications fully specified.** Windows, macOS, and Linux all have concrete commands. Platform detection via `uname` or `$OSTYPE`.

7. **Knowledge file naming with worktree-slug prefix.** Prevents merge collisions cleanly.

8. **Receiving-review is now MANDATORY with explicit invocation.** The reviews.md and skills.md both enforce this, though the timing in step 6 needs fixing (see blocking #2).

9. **Open questions are well-organized.** Resolved items have clear decisions with rationale. Still-open items are genuinely open.

---

## Recommendations

Ordered by priority:

1. **Fix reviews.md stale helm-go reference (Blocking #1).** One-line fix. The document contradicts the core architectural decision from round 2.

2. **Fix receiving-review invocation timing (Blocking #2).** The current wording will cause implementers to invoke the skill before spawning the reviewer instead of before reading findings. This undermines the entire receiving-review protocol.

3. **Decide on `scratch/reviews/` (Blocking #3).** Either give it a purpose or remove it. Vestigial directories confuse implementers.

4. **Add no-permission-asking rule to helm-go (Gap #1).** Low effort, high impact. CC will ask for confirmation during autonomous execution without this.

5. **Define staleness response flow (Gap #4).** Current "notify user" is a dead end. The flow needs a defined state transition.

6. **Fix codeguide-update scope in helm-merge (Gap #3).** The current spec produces an empty diff after merge. Use the checkpoint branch.

7. **Update retry tracking placement (Minor #3).** Move retry updates to where retries actually happen, not end-of-task.

8. **Add plan step granularity guidance (Gap #2) and fabrication detection (Gap #6).** These are defense-in-depth measures. Not urgent but worth adding before implementation.

9. **Clean up minor issues.** Lock file conflict resolution, dimension config location, abandon flow documentation, cross-references.
