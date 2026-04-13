# Proposal 02 — Stabilization Fixes

**Status:** Proposed
**Depends on:** none
**Blocks:** none

## One-line summary

A bundle of small, surgical fixes from the last two autonomous runs that all survive the dual-Opus rewrite (Proposal 05) and are worth landing in their own right: an autonomous-fix policy, a hard worktree-isolation rule, plus four bugs discovered during the gemini-cli-support run — stale `status.md` from Thread B (priority), empty timestamped dirs leaked by `spawn_reviewer` during tests, code-reviewer subagents fabricating timestamps, and the reviewer bulk payload missing non-diff context files. The original Fix C (`mill-spawn.ps1` prose-paragraph parser) was moved into Proposal 07 (Python toolkit) since the Python rewrite solves it natively.

## Background

Fixes A and B came out of the 2026-04-13 "Add functionality to track the status of a child worktree from a parent" run plus the proposal-writing session that followed. Fixes D, E, F, and G came out of the 2026-04-13 gemini-cli-support run. Both runs completed successfully, but a number of distinct concerns surfaced that all share the same shape: small, surgical, independent of the architecture rewrite. Landing them in one proposal keeps the fixes together and avoids churn in the proposal tree.

The original Fix C — a patch to `mill-spawn.ps1`'s task-description parser so it would pick up prose paragraphs instead of only bullet lines — has been **moved into Proposal 07 (Python toolkit)**. Rewriting `mill-spawn` in Python during that migration solves the parser problem natively; patching the PowerShell parser first would be throwaway work. The Fix C section below is kept as a pointer so downstream references don't break; the letter `C` is skipped in the remaining lettering to preserve D/E/F/G cross-references elsewhere in this doc.

(Three other bugs from the track-child-worktree run — `cwd drift`, `relative paths`, `Thread B current_step skip` — are NOT included in this proposal. They are mooted by Proposal 04 and Proposal 05 because the affected code is being rewritten or removed entirely. Fixing them now would be wasted work. Note that the `current_step skip` bug from that run is distinct from Fix D below: Fix D is about **ongoing** status.md updates going silent mid-run, not a single skipped step.)

## The fixes

### Fix A — Autonomous-fix policy for spawned threads

#### What happened

During the track-child-worktree run, Thread B (Sonnet implementer-orchestrator) made **two** out-of-plan code commits to fix bugs in `spawn-agent.ps1` that were blocking its own work:

1. `0461f28 fix(spawn-agent): force array to prevent PS5 scalar unboxing on single-line result` — Thread B couldn't parse the reviewer's JSON line because PowerShell 5 was unboxing a single-line stdout result from `[string[]]` to bare `string`.
2. `0813108` (component) — Thread B couldn't parse the reviewer's JSON line because the reviewer wrapped its result in markdown backticks (` `` ` `` `).

Both fixes are objectively correct and useful. Thread B debugged the symptom, hypothesized the cause, applied a minimal fix, committed, and re-spawned the reviewer successfully. Without the autonomous fixes, the run would have blocked twice and required manual intervention.

But there's no record of the reasoning, no scrutiny dedicated to those specific commits beyond their inclusion in the round-1 reviewer's whole-diff scan, and no automated way for the user to find them post-hoc.

#### Risk profile of "fix-and-continue"

- Surface-tested once. The reviewer spawn worked after the fix — but multi-line stdout, empty stdout, and error stdout may all behave differently after the fix and weren't tested.
- Bypasses dedicated code review. The round-1 reviewer reviewed the fix as one line item among 17 commits' worth of changes — not the level of scrutiny a standalone fix to a critical script deserves.
- No paper trail of reasoning. Symptom, hypothesis, fix description — none recorded. If the fix turns out to be wrong later, no trace to retrace the diagnosis.
- Spiral risk. "I fixed the tool, now I noticed the tool's caller was also wrong, so I fixed that too" is the path to runaway scope expansion in a single run.
- Hides the underlying bug from the user. A "block-and-surface" path forces visibility; a "fix-and-continue" path silently absorbs the problem and you only find it by accident.

#### Tradeoff vs. always-block

If Thread B always blocks on a broken tool, every transient issue with `spawn-agent.ps1` / `claude` / `git` becomes a manual intervention. With autonomy, Thread B unblocks itself and the run completes. That's usually a net win for productivity. The goal is not to ban autonomous fixes — it's to make them **visible** and **bounded**.

#### Compromise design (minimum useful version)

1. **Mandatory commit tagging.** Out-of-plan tool fixes get a `[autonomous-fix]` prefix in the commit subject. Easy to grep, easy to spot in logs.
2. **Final JSON includes `autonomous_fixes: ["sha1", "sha2", ...]`.** When Thread B exits with `phase: complete`, its final JSON line includes the SHAs of any autonomous fixes it made during the run. The user (or mill-go's completion notification) sees them in the report and can decide whether to keep, revert, or expand on them.

These two changes alone give visibility without slowing down the happy path.

#### Stronger version (if the minimum proves insufficient)

1. **Justification file.** Thread B writes `_millhouse/task/reviews/<timestamp>-autonomous-fix-<n>.md` containing: symptom, hypothesis, fix description, why the fix can't wait, what was tested. The file is reviewed alongside the next code-review round.
2. **Hard cap.** Maximum 1 autonomous fix per run. A second one indicates a structural problem and Thread B blocks instead of patching around it. The user investigates manually.
3. **Scope limit.** Allowed: scripts in `plugins/mill/scripts/` that Thread B is actively invoking. Forbidden: source code unrelated to the plan, changes to other tasks' work, changes that cross plugin boundaries.

Start with the minimum. Escalate to the stronger version only if a real out-of-plan fix bites you.

#### Apply to which orchestrator?

- Today's Thread B (Sonnet implementer-orchestrator) gets the policy added to its brief.
- Tomorrow's Thread B (Opus orchestrator after Proposal 05) inherits the policy in its new brief.
- The implementer subprocess (Sonnet/Haiku, fresh-spawn) does NOT get autonomous-fix permission — it's purely mechanical execution. Only the orchestrator can authorize fixes to its own tools.

### Fix B — Worktree isolation rule

#### What happened

mill-go's current `Phase: Setup` step says "commit `tasks.md` from the parent worktree". The natural implementation is `cd <parent-path> && git add tasks.md && git commit && git push`. This works once but corrupts the bash harness's working directory for the entire rest of the session, because cwd persists across Bash tool calls. Subsequent commands then operate on the wrong worktree (parent instead of child), with cascading failures.

The previous run hit this. The Thread B spawn fired against the parent worktree's `spawn-agent.ps1` (which still had a `--bare` bug from before the worktree's own fix), causing a "Not logged in" failure. The brief materialization landed in the parent's `_millhouse/scratch/` and the second spawn attempt failed with "Prompt file not found" from the child.

The deeper issue isn't `cd` vs `git -C` — it's that **the orchestrator was reaching into the parent worktree at all**. A child worktree exists precisely so the branch-of-work is isolated. Reaching into the parent breaks that isolation, lands commits directly on `main` bypassing the feature branch, and creates merge-time surprises.

#### The rule

A session running from a child worktree:

- **MAY** read parent state: `git -C <parent> log/status/show` etc.
- **MAY NOT** edit files in the parent worktree.
- **MAY NOT** commit or push from the parent worktree.
- **MAY NOT** `cd` into the parent worktree (because cwd persistence corrupts the rest of the session).

Even when the skill text says "do X in the parent worktree", that text is the bug — fix the skill, don't follow the bad instruction.

#### Where to encode it

1. **`plugins/mill/skills/conversation/SKILL.md`** — add a "Worktree isolation" section to the response-style rules. Conversation skill is loaded on every startup, so the rule is always present in the agent's working memory.
2. **`plugins/mill/skills/mill-go/SKILL.md`** — remove any remaining instructions to write to the parent worktree. Proposal 05 will rewrite mill-go more substantially, but until then, scrub the existing skill of parent-side writes.
3. **`plugins/mill/skills/mill-merge/SKILL.md` and friends** — `mill-merge` legitimately operates across the parent (it claims `merge.lock`, etc.). Audit it carefully: the only legitimate parent-side writes are the merge commit itself and the lock file, both of which happen via `git -C <parent>` not `cd`.

#### Connection to the autonomous-fix policy

The previous run's autonomous fixes (`0461f28`, `0813108`) were exactly the kind of "tool I need to do my job is broken, fix it" moment the policy is for. Both fixes also happened to be in `plugins/mill/scripts/spawn-agent.ps1`, which is in-scope for the proposed scope-limit. The two fixes are independent but synergistic — together they give "Thread B can fix its own tools, but only specific tools, and you can see what it did".

### Fix C — *moved to [Proposal 07 (Python toolkit)](07-python-toolkit.md)*

The original Fix C was a PowerShell patch for `mill-spawn.ps1`'s task-description parser, which only matched bullet-point lines and therefore produced empty handoff bodies and empty `task_description:` fields on the new prose-paragraph `tasks.md` format. Since Proposal 07 retires `mill-spawn.ps1` entirely and rewrites it in Python, the parser correctness requirement moves there as an acceptance criterion, and no PowerShell patch is needed. See Proposal 07's Migration ordering (`mill-spawn.ps1` is step 1) and Acceptance criteria.

### Fix D — Thread B stops updating `status.md` mid-run (priority bug)

#### What happened

[plugins/mill/doc/modules/implementer-brief.md](../modules/implementer-brief.md) requires Thread B to update `<STATUS_PATH>` at every phase transition (`testing`, `reviewing`, `complete`) and at every step boundary (`current_step`, `current_step_name`, `step-<N>` timeline entry). In practice Thread B writes the first few step entries and then goes silent — `phase:` stays at `implementing` and `current_step` stays at an early step number while many more commits land and the implementer drifts through Phase: Test and into Phase: Review's fixer loop.

**Observed in gemini-cli-support run (2026-04-13):** status.md last updated to `current_step: 8 / step-8 12:10 UTC`. By 12:32 UTC, 14 commits had landed (steps 1–19 with bundling), Phase: Test had completed, code-review round 1 had finished with REQUEST_CHANGES, the round-1 fixer commit had been pushed, and code-review round 2 was already returning. Status.md was 22+ minutes stale and pointing at the wrong phase the entire time. From the operator's view (mill-go Thread A, the user, or any external monitor), Thread B looked hung. The only reliable signals were `git log` and scratch-file mtimes — neither of which is what the brief contract promises.

#### Why this is the priority bug

The whole point of status.md is operator visibility into a long autonomous run. When status.md goes stale, the operator can't tell "stalled" from "working" without poking at git internals. The brief's stall-detection rule (10 min of no status.md mtime advance) becomes a false-positive generator. Fix E and Fix F below are observability / hygiene issues; Fix D breaks the entire orchestrator → operator contract.

#### Fix candidates

- **Hard precondition on commit.** Wrap the per-step commit logic so it cannot complete a step's commit without first writing the `current_step` / timeline entry. If the model "forgets," the commit doesn't happen.
- **Explicit phase-transition writes.** Add phase-transition writes to the materialized brief at the top of Phase: Test and Phase: Review (Thread B currently has these as bullets in section 6 / 7 but evidently treats them as soft).
- **Take status.md updates out of the model's hands entirely.** Have `spawn-agent.ps1` (or a wrapper) tail the agent's tool calls and emit synthetic status.md updates on commit-tool-call boundaries. Removes the model's freedom to skip them.

Same lesson as Fix F below: any rule that depends on the model "remembering" to do housekeeping is unreliable. Bake it into the protocol where the model has no choice. Start with the hard-precondition option (cheapest, most local); escalate to the tool-call-tailing option only if it still drifts.

### Fix E — `spawn_reviewer.dispatch_workers` leaks empty timestamped dirs at cwd during tests

#### What happened

`dispatch_workers` in [plugins/mill/scripts/spawn_reviewer.py](../../scripts/spawn_reviewer.py) calls `os.makedirs(os.path.join(reviews_dir_base, ts))` **before** validating its `prompt_file_path` / `materialized_prompt` parameters. Two validation tests in [plugins/mill/scripts/test_spawn_reviewer.py](../../scripts/test_spawn_reviewer.py) (`test_tool_use_missing_prompt_file_raises`, `test_bulk_missing_materialized_prompt_raises`) pass `"."` as `reviews_dir_base`. Result: every full test run leaks two empty `YYYYMMDD-HHMMSS/` directories at the process cwd — which is the repo root during normal test invocation. Observed in the gemini-cli-support implementation run: 10 empty dirs like `20260413-120323/` appeared at repo root across ~5 test invocations.

The dirs are not gitignored because they land at repo root, not under `_millhouse/`. They surfaced visually in the VS Code file tree during the Thread B run.

#### Fix

Move the `prompt_file_path` / `materialized_prompt` validation above the `ts` / `os.makedirs` block in `dispatch_workers`. Also update the two validation tests to use `tempfile.TemporaryDirectory()` as `reviews_dir_base` for defense-in-depth (even though after the fix an unsuccessful dispatch never touches the filesystem).

### Fix F — code-reviewer subagent fabricates timestamps instead of running `date -u`

#### What happened

The code-reviewer prompt template [plugins/mill/doc/modules/code-review.md:85](../modules/code-review.md#L85) explicitly says "Generate the timestamp for the filename via shell: `date -u +"%Y%m%d-%H%M%S"` (see `@mill:cli` timestamp rules — never guess timestamps)." The instruction is also present at line 15560 of the materialized prompt at `_millhouse/scratch/code-review-prompt-r2.md`. Despite this, the reviewer subagent (sonnet, spawned via `spawn-agent.ps1 -Role reviewer` from Thread B's Phase: Review loop) fabricates round-hour timestamps instead of calling the shell.

**Observed in gemini-cli-support run (2026-04-13):**

- `_millhouse/task/reviews/20260413-120000-code-review-r1.md` (claimed 12:00:00 UTC, actual mtime ~12:25 UTC)
- `_millhouse/task/reviews/20260413-130000-code-review-r2.md` (claimed 13:00:00 UTC, actual mtime ~12:32 UTC; current real time ~12:41 UTC)
- By contrast, Thread B's own fixer report `20260413-122817-code-fix-r1.md` is correctly shell-generated (Thread B uses Bash to compute the timestamp).

#### Scope

The bug is in the code-reviewer subagent thread spawned by `spawn-agent.ps1 -Role reviewer`, not in Thread B itself. Plan-reviewer and discussion-reviewer subagents may share the same defect — cross-check by inspecting their output filenames against actual mtimes.

#### Likely root cause

Reviewer subagent reads the prompt instruction but skips the Bash tool call. May correlate with reviewers running with `-MaxTurns 20` (default) where the agent treats Bash invocations as "expensive" and economizes incorrectly. The `@mill:cli` skill may not be loaded into the spawn-agent.ps1 reviewer subprocess context.

#### Fix

Remove the agent's freedom to invent the filename. The orchestrator (Thread B / mill-go / mill-start) pre-computes the full output path (`_millhouse/task/reviews/<shell-generated-ts>-<phase>-review-r<N>.md`) before spawning the reviewer, and substitutes it into the materialized prompt as a `<REVIEW_FILE_PATH>` token. The reviewer's instructions become "write your report to `<REVIEW_FILE_PATH>` and return that exact path in the JSON line." There is no decision left for the subagent to get wrong.

Strengthening the prompt language ("CRITICAL: never guess timestamps") is **not** a candidate. The instruction is already explicit and is being ignored. Any fix that leaves the timestamp computation in the subagent's hands will fail the same way.

**Touches:** `plugins/mill/doc/modules/code-review.md`, `plan-review.md`, `discussion-review.md` (remove the "Generate the timestamp" instruction; replace `<timestamp>` placeholders with the new `<REVIEW_FILE_PATH>` token); `plugins/mill/skills/mill-go/SKILL.md` (Phase: Plan Review materialization step pre-computes and substitutes `<REVIEW_FILE_PATH>`); `plugins/mill/doc/modules/implementer-brief.md` (Phase: Review materialization step does the same); `plugins/mill/skills/mill-start/SKILL.md` (discussion-review materialization).

### Fix G — Reviewer bulk payload must be an explicit file list, not git-diff-driven

#### What happened

The code-reviewer is handed a bulk payload built from the implementation `git diff`. This has two failure modes — one narrow, one structural.

**Narrow failure:** files that the implementer **read** but didn't modify — supporting modules, type definitions, configuration that shapes the modified code's behavior — are not in the payload. When the reviewer asks "does this call site pass the right shape?" and the called function's source isn't in the bundle, the reviewer guesses. The guess is sometimes wrong and surfaces as a false-positive finding, or (worse) a real issue missed because the reviewer assumed a shape that happened to match the change.

**Structural failure:** because the payload *is* `git diff`, the review pipeline only works on changes that have been committed. When a parallel thread wanted to compare bulk-review vs tool-use-review on **identical content**, it proposed creating a throwaway WIP commit purely so `git diff` would return the files — then suggested `git reset --soft HEAD~1` afterward to undo it. That workaround is the design smell: the reviewer is forcing the rest of the system to contort git state so it can see the code. Same hazard applies to reviewing uncommitted work, staged-but-not-committed hunks, split feature branches, or any case where the files of interest aren't exactly what `git diff HEAD` returns.

#### Fix

The reviewer's input is an **explicit, authoritative list of file paths**, supplied to the orchestrator. `git diff` is at most one *optional helper* for computing that list — never the source of truth. Concretely:

1. **Primitive:** a file-list bulker that takes a plain list of paths (absolute or repo-relative) and produces the bulk payload by `cat`-ing each file with a header. Zero git dependency. This is the lowest layer; everything else builds on it. Lives in the Python toolkit (Proposal 07) as something like `millpy/bulk_payload.py`.
2. **Plan-declared list:** the plan format grows a `Read:` / `Files:` section that lists the files the reviewer should see for a given review round — both the ones being rewritten AND the ones that are just load-bearing context. The planner declares this up front; the orchestrator reads the list at Phase: Review materialization and hands it to the file-list bulker.
3. **`git diff` becomes optional syntactic sugar.** For the narrow case where "the files of interest" really are "whatever the last N commits touched", the orchestrator is allowed to call a helper like `compute_file_list_from_diff(base, head)` that walks `git diff --name-only` and produces a list — which then goes into the same file-list bulker. But this is one computation method among several, invoked by explicit choice, not baked into the review path.

No review round ever asks for a commit that wouldn't otherwise exist. No thread ever proposes `git reset --soft HEAD~1` as a cleanup step. If that pattern surfaces, it is a signal that the file-list abstraction is being bypassed — push back on the design, don't accommodate the workaround.

#### Open design question (deliberately left open)

What is the *smartest* way to compute the file list? Plan declaration is the baseline — it works, it's explicit, and it makes the dependency on context visible. But it also asks the planner to know up front which files the reviewer will need, which is a nontrivial judgement call. Smarter options that may beat plain plan declaration:

- **Import-walk.** For typed languages, walk imports from the plan's `Touches:` files to depth N and include anything referenced. Accurate but language-specific.
- **`Touches:` expansion.** Planner lists files *written*; orchestrator walks same-module or same-directory siblings automatically.
- **LSP-driven.** Run a language server against the touch set and ask it "what other files do you need to type-check these?" High accuracy, high setup cost.
- **Retry-with-more.** Start with the minimal list (just the diff); if the reviewer output contains phrases like "I don't have the source of X", re-spawn with X added. Self-correcting but burns one wasted review round.

None of these are settled in this proposal. The requirement is only that the underlying primitive (file-list bulker) be agnostic to how the list was computed, so smarter list-computation strategies can slot in later without touching the reviewer path.

**Touches:** `plugins/mill/doc/modules/plan-format.md` (add `Read:` / `Files:` section), `plugins/mill/skills/mill-plan/SKILL.md` or current plan-writing skill (teach the planner to populate the list), the orchestrator's bulk-payload materialization in Phase: Review (call the file-list bulker with the plan's list; never build the payload straight from `git diff`). The file-list bulker primitive itself lives in Proposal 07 (Python toolkit) — this Fix G is the consumer, Proposal 07 is the provider.

## Goals

- Add `[autonomous-fix]` commit tagging requirement to the orchestrator brief (current and future).
- Add `autonomous_fixes` array to the orchestrator's final JSON contract.
- Update mill-go's completion notification to relay the count and SHAs of any autonomous fixes.
- Add the worktree-isolation rule to `conversation/SKILL.md`.
- Audit existing skills for parent-side writes that aren't legitimately in mill-merge / mill-cleanup territory; fix anything found.
- Make `status.md` updates unskippable in Phase: Implement / Test / Review (Fix D). Start with the commit-precondition variant; escalate if needed.
- Move the `prompt_file_path` / `materialized_prompt` validation in `dispatch_workers` ahead of the `os.makedirs` call, and swap the two leaking validation tests to use `tempfile.TemporaryDirectory()` as `reviews_dir_base` (Fix E).
- Introduce a `<REVIEW_FILE_PATH>` token in the code-review / plan-review / discussion-review prompt templates and substitute it from the orchestrator before spawning the reviewer (Fix F). Remove the "Generate the timestamp" instruction from those templates.
- Rewire the reviewer bulk-payload pipeline so it consumes an explicit file list instead of `git diff` (Fix G). The plan format grows a `Read:` / `Files:` section; the orchestrator passes that list to a file-list bulker primitive (provided by Proposal 07); `git diff`-derived lists remain available as an optional helper but never as the default source of truth.

## Non-goals

- Implementing the stronger version of the autonomous-fix policy (justification file, hard cap, scope limit). Wait until the minimum version proves insufficient.
- Rewriting mill-go's overall flow. That's Proposal 04+05.
- Adding similar policies to other skills (mill-start, mill-cleanup, etc.) — only the orchestrator and implementer can self-modify code mid-run.
- Settling the "smartest way to compute the reviewer file list" question. Fix G locks in the primitive (explicit file list, git-agnostic) and the baseline (planner declaration). Import-walking, LSP-driven, and retry-with-more strategies are out of scope for this proposal but are explicitly reserved as future work that will slot in on top of the same primitive.

## Open questions for the discussion phase

1. Is the `[autonomous-fix]` prefix sufficient, or should there also be a Git trailer (`Autonomous-Fix: true`) for tooling that greps commit bodies, not just subjects?
2. Should the orchestrator also write a brief one-line note about each autonomous fix into `_millhouse/task/status.md` (e.g. as a `autonomous_fix_<n>:` field), so the live status reflects them in real time, not just at end-of-run?
3. The worktree-isolation rule needs an explicit "exception" for mill-merge and mill-cleanup. Should those exceptions be in the rule itself ("...except mill-merge and mill-cleanup, which need to operate on the parent's merge state"), or should those skills explicitly opt in via a comment that acknowledges they're an exception?
4. Fix D: should the first implementation be the hard commit-precondition (cheapest, model still runs the write) or go straight to tool-call tailing in `spawn-agent.ps1` (more invasive, but removes model agency entirely)? The commit-precondition approach is less work but still trusts the model to write *something*; tool-call tailing is the only option that fully solves the problem.
5. Fix F: should `<REVIEW_FILE_PATH>` be substituted by the orchestrator into the materialized prompt text, or passed as an environment variable that the reviewer prompt references? The substitution path is simpler; env-var path is more uniform with other parameters but requires the prompt template to grow a new convention.
6. Fix G: does the `Read:` / `Files:` list have per-file annotations (e.g. `- src/foo.ts — interface definition referenced by Bar`) or is it just a flat path list? Annotations help reviewers prioritize but bloat the plan; flat list is simpler but loses information.
7. Fix G: where exactly does the file-list bulker primitive live in Proposal 07 — `millpy/bulk_payload.py`, part of `claude_subprocess.py`, or a new module? Leaning toward standalone module so the bulker can be called from non-review paths too (e.g. scratchpad context dumps).

## Acceptance criteria

- The implementer-brief template (current Sonnet version, in [plugins/mill/doc/modules/implementer-brief.md](../modules/implementer-brief.md)) has a section explaining when autonomous fixes are allowed and the tagging requirement.
- A test run that triggers an autonomous fix (e.g. inject a known-broken `spawn-agent.ps1` quirk) produces a commit with `[autonomous-fix]` in the subject and a final JSON line containing that commit's SHA.
- `conversation/SKILL.md` has a "Worktree isolation" section; running a session from a child worktree and asking the agent to commit a parent-side change produces a refusal with reference to the rule.
- Grep across `plugins/mill/skills/` finds zero `cd <parent>` patterns and zero parent-side `git add/commit/push` outside of mill-merge and mill-cleanup.
- Fix D: a full end-to-end run produces a `_millhouse/task/status.md` whose final `current_step` matches the final step in the plan, with timeline entries for every step between. No gap greater than one step between the last timeline entry and the commit log at any point during the run. Phase transitions (`implementing → testing → reviewing → complete`) are all reflected in status.md.
- Fix E: running the full `test_spawn_reviewer.py` suite from repo root leaves zero new directories at repo root.
- Fix F: three consecutive code-review runs (r1, r2, r3) produce review files whose filename timestamps match their actual mtimes to within 5 seconds. The reviewer prompts contain no `date -u` or "Generate the timestamp" instruction.
- Fix G: the reviewer bulk-payload pipeline accepts an explicit file list and produces a payload that contains exactly those files, with no involvement from `git diff`. A plan with a populated `Read:` / `Files:` section produces a reviewer payload whose file set equals that list. A review round can be run on uncommitted files with no commits made in the process — verified by a smoke test that reviews a dirty working tree without creating any new commit objects.

## Risks and mitigations

- **Models ignore the commit tag rule** if the brief language is weak. Mitigation: same lesson as Fix F — make it load-bearing, with a stated consequence and a "before X you must Y" precondition format.
- **Worktree-isolation rule is too strict for legitimate use cases.** Mitigation: explicit exceptions for mill-merge / mill-cleanup, documented in both the rule and the affected skills.
- **Audit misses something.** Mitigation: the audit is small (≤10 skill files) and the grep pattern is unambiguous.
- **Fix D's commit-precondition variant still trusts the model.** If it forgets to call the wrapper, nothing changes. Mitigation: gate commit via `spawn-agent.ps1`'s tool-call hook so the hook enforces it regardless of model intent. This is the escalation path baked into the fix design.
- **Fix F's `<REVIEW_FILE_PATH>` token collides with existing prompt content.** Mitigation: pick a token that's clearly non-English (`<REVIEW_FILE_PATH>`, full caps, angle brackets) and grep all three review prompt templates before substituting.
- **Fix G's file list rots.** The planner adds a file to the list for the initial review, but later changes make it no longer relevant, and the list is never pruned. Mitigation: accept this. A stale entry costs a few extra tokens in the reviewer payload but doesn't harm correctness. Pruning is a nice-to-have for later.
- **Fix G's primitive lives in a different proposal.** The file-list bulker is in Proposal 07 (Python toolkit); the plan-format and orchestrator-wiring changes are in Proposal 02. If Proposal 02 ships first, Fix G has to wait for the primitive to land; conversely, Proposal 07 can ship without Proposal 02's plan-format change and the primitive will just be unused by the review path until 02 lands. Mitigation: explicit ordering note in Dependencies; don't mark Fix G as done until both halves are in place.

## Dependencies

- None for landing. This proposal can ship before, after, or in parallel with any other proposal.
- **Proposal 07 (Python toolkit) absorbs the original Fix C** and provides Fix G's file-list bulker primitive. Fix G's plan-format and orchestrator-wiring changes live in this proposal, but the underlying `millpy/bulk_payload.py` module (or equivalent) is Proposal 07's responsibility. Fix G is considered done only when **both** halves are in place. If Proposal 07 has not landed yet when this proposal ships, the parser correctness requirement (original Fix C) is carried as an acceptance criterion on Proposal 07, and Fix G's wiring waits for Proposal 07's bulker primitive to exist before it can be wired through.
- After Proposal 05 lands, the autonomous-fix policy (Fix A) and the status.md invariant (Fix D) need to be re-applied to the new Opus orchestrator brief — but the *content* is the same. The `<REVIEW_FILE_PATH>` substitution (Fix F) and bulk-payload union (Fix G) also live in the new orchestrator; re-port the same logic.
