# Helm Design Review — Round 4 Result

---

## Blocking Issues

### 1. No final commit after code review fixes, codeguide update, and knowledge writes

**What:** helm-go commits each plan step during implementation (step 3), but after code review fixes (step 5), codeguide update (step 6), knowledge entry (step 7), and decisions register (step 8), there is no commit. These all produce changes to tracked files that remain uncommitted.

**Where:** skills.md helm-go steps 5-8.

**Why:** After code review, the reviewer may request changes. The implementing agent "fixes accepted issues, re-verifies, re-reviews." Those fixes produce new code changes. Then codeguide-update modifies docs. Knowledge entries and decisions are written to `_helm/knowledge/` (tracked). None of this is committed. The worktree is left with uncommitted changes — which breaks the resume protocol (step 3's per-step commits enable crash recovery, but post-review work has no such protection) and means `helm-merge` will encounter dirty state. The open-questions.md resolved decision says the sequence is "implement -> verify -> code-review -> codeguide-update -> commit" — that final commit is missing from the actual flow.

**Suggestion:** Add a step between current steps 8 and 9: "Commit code review fixes, codeguide updates, knowledge entry, and decisions with message: `chore: post-review cleanup for <task-title>`." Also specify the commit message for code review fix iterations — when the reviewer requests changes in round 2, the fix-and-recommit cycle needs a defined message format.

### 2. Code reviewer diff scope is uncomputable from the spec

**What:** Step 5 says "Spawn code-reviewer Agent with the diff (since plan start, not just last step)" but doesn't define how to compute "since plan start." Each implementation step commits individually, so there's no single uncommitted diff.

**Where:** skills.md helm-go step 5.

**Why:** An implementer needs to know the exact `git diff` command. The plan has a `started:` timestamp, but `git diff` doesn't accept timestamps. The implementer must record the commit hash before step 1 begins, then compute `git diff <saved-hash>..HEAD`. Without this, two reasonable implementers would produce different diffs: one might diff against the parent branch (too broad — includes other tasks), another might diff only the last step's commit (too narrow).

**Suggestion:** Add to helm-go flow before step 1 (after resume protocol): "Record `PLAN_START_HASH=$(git rev-parse HEAD)`. This is the baseline for code review." Then in step 5: "Compute diff: `git diff $PLAN_START_HASH..HEAD`." If resuming, PLAN_START_HASH should be the commit before the first plan step's commit (discoverable from `git log`).

### 3. helm-start has no step for reading the handoff brief in worktree context

**What:** When a user runs `helm-start` in a new worktree, worktrees.md says "CC reads the brief as background context." But the helm-start skill flow in skills.md has no step for this. Step 1 jumps straight to "Read tasks from GitHub Projects board."

**Where:** skills.md helm-start flow (missing between entry and step 1), worktrees.md "Working" section.

**Why:** An implementer writing the SKILL.md for helm-start will follow the flow in skills.md. Without an explicit brief-reading step, the handoff context is lost. Additionally, when a brief exists, it already identifies the task and may contain discussion context — the skill should detect this and skip task selection (step 1) and potentially parts of the explore phase (step 3) if the brief already covers them.

**Suggestion:** Add step 0 to helm-start: "Check if `_helm/scratch/briefs/handoff.md` exists. If yes: read it. The brief's `## Issue` identifies the task — select it directly (skip the selection prompt in step 1). The brief's `## Discussion Summary` is prior context — incorporate it, but still run your own explore phase and ask your own clarifying questions. The brief informs but does not constrain."

### 4. `_helm/config.yaml` template in kanban.md is incomplete

**What:** The config template in kanban.md step 6 only includes `worktree:` and `github:` sections. But `models:` (defined in open-questions.md) and `notifications:` (defined in notifications.md) are also part of the config.

**Where:** kanban.md step 6 config template vs. open-questions.md "Agent model selection" and notifications.md "Configuration."

**Why:** An implementer following helm-setup will produce a config file missing the model configuration and notification settings. When helm-go later tries to read `models.code-review` to select the reviewer model, the key won't exist. The config template must be the single source of truth for the file's structure.

**Suggestion:** Add to the kanban.md step 6 config template:
```yaml
models:
  session: opus
  plan-review: sonnet
  code-review: sonnet
  explore: haiku

notifications:
  slack:
    enabled: false
    webhook: ""
    channel: ""
  toast:
    enabled: true
```
And add a step in helm-setup between step 8 (ask prefix) and step 9 (report) to ask about notification preferences.

---

## Ambiguities

### 1. How helm-go finds the plan file

**What:** Step 1 says "Read plan" but doesn't specify how to locate it. Plans are in `_helm/scratch/plans/<timestamp>-<slug>.md` (gitignored). If there are plans from different tasks, or if the session is resumed and context is fresh, the implementer needs a discovery mechanism.

**Where:** skills.md helm-go step 1.

**Options:** (A) Read the GitHub issue (from status.md's `issue:` field) and find the plan comment — but this is a summary, not the full plan file. (B) Glob `_helm/scratch/plans/*.md` and pick the most recent with `approved: true`. (C) Store the plan path in `_helm/scratch/status.md`.

**Recommendation:** Option C. Add `plan: _helm/scratch/plans/<timestamp>-<slug>.md` to status.md. helm-start writes it when the plan is approved. helm-go reads the path from status.md. This is explicit, survives context compression, and doesn't require parsing GitHub comments.

### 2. status.md format has two conflicting definitions

**What:** worktrees.md defines a simple 6-field format. notifications.md defines a detailed format with additional fields: `current_step`, `current_step_name`, `steps_total`, `steps_done`, `retries:`, `last_updated`.

**Where:** worktrees.md "Status Tracking" section vs. notifications.md "Status file" section.

**Options:** (A) Use the simple format from worktrees.md. (B) Use the detailed format from notifications.md.

**Recommendation:** Option B — the detailed format from notifications.md. It has everything the simple format has plus progress tracking and retry state, which are needed for resume protocol and helm-status. Update worktrees.md to reference notifications.md as the canonical format definition, or move the canonical definition to its own section and have both files reference it.

### 3. `_helm/scratch/reviews/` created but never populated

**What:** kanban.md step 6 creates `_helm/scratch/reviews/` as part of the directory structure. But no skill writes review results there — code review and plan review are agent-to-agent (results returned directly in context).

**Where:** kanban.md step 6 `mkdir` command, open-questions.md directory structure (no longer lists it, but kanban.md still creates it).

**Options:** (A) Store code-reviewer and plan-reviewer findings in `scratch/reviews/<timestamp>-<type>.md` for audit trail and resume. (B) Remove from the `mkdir` command.

**Recommendation:** Option A. Store review findings for two reasons: (1) resume protocol — if helm-go crashes after code review round 1, a resumed session can read the findings instead of re-running the reviewer. (2) audit trail — the user can see what the reviewer said. Define the format: `<timestamp>-plan-review-round-<N>.md` and `<timestamp>-code-review-round-<N>.md`.

### 4. helm-start task filtering

**What:** kanban.md says helm-start "Filters to Backlog column (or user-specified column)" but `gh project item-list` returns all items. The filtering logic (parse JSON, match status field to "Backlog") is not specified.

**Where:** skills.md helm-start step 1, kanban.md "Reading tasks."

**Options:** (A) Use `gh project item-list --format json` and filter client-side with `jq`. (B) Use a GraphQL query with field-value filtering.

**Recommendation:** Option A — simpler and the `gh` CLI handles pagination. Add the filtering command: `gh project item-list <number> --owner <owner> --format json | jq '[.items[] | select(.status == "Backlog")]'`. Note: the exact JSON structure from `gh project item-list` should be documented with a sample output so the implementer knows the field names.

---

## Missing Specs

### 1. Plugin directory structure and registration

**What:** No spec exists for `plugins/helm/.claude-plugin/plugin.json`, `plugins/helm/settings.json`, skill directory layout, or how the plugin registers its skills.

**Why:** An implementer needs to know: What skills does plugin.json declare? What permissions does settings.json grant (Bash for `gh` commands? Skill invocations for codeguide/code/git?)? How are skill directories named (`helm-start/SKILL.md` vs `start/SKILL.md`)? The existing plugins (conduct, codeguide, taskmill) each have these files — but Helm's requirements are different (Agent spawning, GraphQL calls, worktree creation).

**Suggestion:** Add a `plugins/helm/` section to the design (or a new `modules/plugin-structure.md`) that specifies:
- `plugin.json`: name, description, version, skill list
- `settings.json`: permissions needed (at minimum: `Bash(gh *)`, `Bash(git worktree *)`, `Bash(git branch *)`, `Bash(code *)`, `Skill(helm:*)`, `Skill(codeguide:*)`, `Skill(code:*)`, `Skill(git:*)`, `Agent(*)`)
- Skill directory mapping: `skills/helm-start/SKILL.md`, `skills/helm-go/SKILL.md`, etc.
- Whether hooks are needed (e.g., blocking direct writes to `_helm/config.yaml` like Taskmill does for backlog.md)

### 2. helm-go plan-start commit hash for resume

**What:** The resume protocol (step 1-4) identifies completed steps by matching commit messages. But there's no mechanism to find the pre-implementation commit hash needed for the code review diff (blocking issue #2) during a resume.

**Why:** On fresh start, recording `PLAN_START_HASH` is straightforward. On resume, the implementer needs to reconstruct it: find the commit just before the first plan step commit. This requires knowing the first step's commit message and finding its parent. The logic isn't specified.

**Suggestion:** Store `plan_start_hash` in `_helm/scratch/status.md` when helm-go first begins. On resume, read it from there. This is simpler and more reliable than reconstructing from git log.

### 3. helm-start explore phase lacks codeguide entry point

**What:** Step 3 says "Use the codeguide navigation pattern: Overview -> module doc -> Source section -> code (see codeguide.md)" but doesn't specify the entry point: where is Overview.md? What if it doesn't exist?

**Why:** codeguide.md specifies the pattern and has a "Conditional" section stating codeguide is skipped if `_codeguide/Overview.md` doesn't exist. But skills.md step 3 doesn't mention this conditional. An implementer needs: "If `_codeguide/Overview.md` exists, follow the navigation pattern. Otherwise, explore using git log, file structure, and grep."

**Suggestion:** Add the conditional check explicitly in helm-start step 3 and helm-go step 2.

### 4. What happens when helm-go finishes all tasks in a worktree

**What:** Step 12 says "If more planned tasks: pick next, repeat from step 1." But what does "more planned tasks" mean? Is it tasks in the Planned column on the kanban board? Tasks with approved plans in `_helm/scratch/plans/`? And when there are no more tasks: does helm-go just stop, or does it notify, or suggest helm-merge?

**Why:** A worktree might have one task or many. The transition from "last task done" to "ready for merge" isn't defined beyond step 9 (phase = complete). Should helm-go set phase = "ready-to-merge"? Post a notification? Suggest the user run helm-merge?

**Suggestion:** After the last task completes (no more planned tasks), helm-go should: (1) set status.md phase to `ready-to-merge`, (2) post a comment on the GitHub issue, (3) send an info notification: "[helm] <worktree> ready to merge — all tasks complete." Add this as a "Completion" section after the execution flow.

### 5. No spec for `_helm/changelog.md`

**What:** open-questions.md lists "Changelog format" as still open. The directory structure lists `_helm/changelog.md` as tracked. But no format is defined, and no skill writes to it.

**Why:** Taskmill's changelog (`_taskmill/changelog.md`) is a dated log of completed work — useful for PR descriptions and work journals. If Helm carries this over, the format needs defining. If not, remove it from the directory structure.

**Suggestion:** Decide and document. Recommendation: keep it, define a simple format (date + task title + bullet summary), and add a write step to helm-go between step 10 (update GitHub issue) and step 11 (knowledge synthesis). Taskmill's mill-log skill reads the changelog — Helm could reuse or adapt that.

### 6. `helm-setup` auto-detection of user vs. organization owner

**What:** kanban.md step 5 uses `user(login:)` for user-owned repos and notes "For org-owned repos, use `organization`." But helm-setup doesn't auto-detect which type the owner is.

**Why:** Round 3 minor issue #1 flagged this. A user running helm-setup will hit a GraphQL error if their repo is org-owned and the query uses `user()`. Auto-detection is one API call: `gh api users/<owner> --jq '.type'` returns "User" or "Organization".

**Suggestion:** Add to helm-setup between steps 4 and 5: "Detect owner type: `gh api users/<owner> --jq '.type'`. Use `user()` or `organization()` accordingly in step 5's GraphQL query."

---

## Strengths

1. **All round 2 and round 3 blocking issues are resolved.** helm-go is cleanly autonomous with explicit no-permission-asking rule. Merge locking is fully specified. Codeguide ordering is consistent. Receiving-review timing is correct (spawn reviewer, then load skill, then read findings). reviews.md no longer has the stale helm-go reference.

2. **Systematic debugging protocol is genuinely actionable.** Four phases (Reproduce -> Trace backward -> One hypothesis at a time -> Targeted fix) with concrete stopping conditions ("After 3 failed hypotheses: STOP"). This is one of the strongest sections in the design — it prevents the common CC failure mode of shotgunning changes.

3. **Coherence approach is pragmatic and well-justified.** Replacing 13 parallel dimension agents with a strengthened code reviewer + codeguide context is the right call for sequential execution. The rationale in coherence.md is clear: Autoboard's model is for parallel sessions that can't see each other's work; Helm's sequential model doesn't need it. The escape hatch (lightweight single-agent audit for merges to main) is noted.

4. **Code reviewer definition is thorough and checkable.** Utility duplication check with codeguide Overview, pattern consistency, TDD verification, test thoroughness with specific BLOCKING criteria (happy-path-only, implementation-mirroring, shallow assertions). The "grep codebase for existing implementations" instruction is concrete.

5. **Failure classification with distinct response strategies.** Four categories (permission/config, code error, upstream dependency, review escalation) with clear routing. The key insight — "don't retry config errors" — prevents wasted cycles.

6. **Per-step commits with resume protocol.** Committing after each plan step and using commit message matching for resume is simple, reliable, and uses native git. No custom state machinery needed beyond status.md.

7. **Receiving-review protocol is production-ready.** Decision tree, forbidden dismissals, legitimate pushback criteria — all adopted from Autoboard with clear adaptation. The "fix everything, only escape is proven harm" principle with specific examples of forbidden rationalizations is strong.

8. **Handoff brief format is well-designed.** The template in plans.md covers everything the receiving session needs (issue, parent, discussion summary, knowledge, codeguide modules, config) without over-constraining. "The brief informs but does not constrain" is a good principle.

9. **Plan step granularity guidance added.** "Prefer one file per step" with the plan reviewer enforcing it. This was a gap in round 3; now addressed in plans.md.

10. **helm-abandon is well-specified.** 8 steps with safety checks (uncommitted changes, unmerged work), user confirmation, and kanban/GitHub cleanup. This was missing entirely before round 3.

---

## Implementation Order

Build in this order. Each phase produces a testable artifact.

### Phase 1: Plugin skeleton + helm-setup
1. **Plugin structure:** Create `plugins/helm/.claude-plugin/plugin.json`, `settings.json`, skill directory stubs. Model after the conduct plugin but with Bash permissions for `gh` and `git worktree`.
2. **helm-receiving-review:** Extract the protocol from reviews.md into `skills/helm-receiving-review/SKILL.md`. This is a dependency for helm-start and helm-go.
3. **helm-setup:** Implement the 9-step flow from kanban.md. This is the entry point for all users — nothing else works without `_helm/config.yaml`.
4. **helm-add:** Simple one-shot skill. Validates that helm-setup worked (config readable, GitHub API accessible).

**Testable:** Run helm-setup on a real repo, create tasks with helm-add, verify board works.

### Phase 2: Design phase (helm-start)
5. **helm-start (no worktree):** Implement the full interactive flow — task selection, explore, discuss, plan writing, plan review loop. This is the most complex interactive skill.
6. **Plan reviewer agent:** Implement the agent definition from reviews.md. Test by running plan review during helm-start.

**Testable:** Run helm-start, discuss a task, produce an approved plan.

### Phase 3: Execution phase (helm-go)
7. **helm-go (core loop):** Implement the execution flow — plan reading, test baseline, per-step implementation with TDD, per-step commits, resume protocol.
8. **Code reviewer agent:** Implement the agent definition from reviews.md. Test within helm-go.
9. **helm-go (post-loop):** Codeguide update, knowledge writing, decisions register, final commit, kanban updates.

**Testable:** Run helm-go on an approved plan, verify all steps execute, code review passes, knowledge is written.

### Phase 4: Lifecycle management
10. **helm-commit:** Simple, mirrors mill-commit.
11. **helm-merge:** Full merge flow from merge.md. Test with a real worktree merging to parent.
12. **helm-start -w (worktree mode):** Worktree creation, brief writing, VS Code launch. Depends on helm-merge being ready (the worktree lifecycle needs merge to be complete).
13. **helm-status:** Read-only dashboard. Simple once status.md is well-defined.
14. **helm-abandon:** Cleanup skill.

**Testable:** Full cycle — helm-start -w, helm-start in worktree, helm-go, helm-merge back.

### Phase 5: Polish
15. **Notifications (Slack + toast):** Add notification hooks to helm-go's escalation paths.
16. **Knowledge synthesis:** Implement the 5-entry threshold synthesis.

### Minimum viable subset
**helm-setup + helm-add + helm-start (no worktree) + helm-receiving-review + helm-go + helm-commit.** This gives you the full design -> execute -> commit cycle without worktrees or merge. Worktrees are powerful but not required for single-stream work.
