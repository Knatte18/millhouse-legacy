# Proposal 02 — Stabilization Fixes

**Status:** Proposed
**Depends on:** none
**Blocks:** none

## One-line summary

Three small, surgical fixes that survive the dual-Opus rewrite (Proposal 05) and are useful in their own right: an autonomous-fix policy for spawned implementer/orchestrator threads, a hard worktree-isolation rule encoded in the workflow skills, and a `mill-spawn.ps1` parser fix so prose task descriptions are picked up (today only bullet-point descriptions are extracted, so the new tasks.md format produces empty handoff/status bodies).

## Background

These came out of running the "Add functionality to track the status of a child worktree from a parent" task on 2026-04-13, plus one bug discovered immediately afterward when writing the proposal docs themselves. The run completed successfully, but several distinct concerns surfaced. All three apply to **any** future orchestrator design (sonnet today, Opus after Proposal 05), so they're worth landing now even though the architecture is changing.

(Three other bugs from that same run — `cwd drift`, `relative paths`, `Thread B current_step skip` — are NOT included in this proposal. They are mooted by Proposal 04 and Proposal 05 because the affected code is being rewritten or removed entirely. Fixing them now would be wasted work.)

## The three fixes

### Fix A — Autonomous-fix policy for spawned threads

#### What happened

During the previous run, Thread B (Sonnet implementer-orchestrator) made **two** out-of-plan code commits to fix bugs in `spawn-agent.ps1` that were blocking its own work:

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

### Fix C — `mill-spawn.ps1` parser ignores prose task descriptions

#### What happened

After the previous run completed and `tasks.md` was rewritten in a new concise format (one task = one heading + a prose paragraph + a markdown link to a proposal doc), spawning the first task via `mill-spawn` produced a handoff file with **no body content**:

```
# Handoff: Gemini CLI support + ensemble reviewer

## Issue
Gemini CLI support + ensemble reviewer

## Parent
Branch: main
Worktree: C:\Code\millhouse

## Discussion Summary
Gemini CLI support + ensemble reviewer

## Config
- Verify: N/A
- Dev server: N/A
```

Every "content" field is just the task title repeated. The actual task description (a paragraph explaining what the task does) is missing entirely.

#### Root cause

The parser in `plugins/mill/scripts/mill-spawn.ps1` lines 62–71 extracts the task description by matching **only bullet-point lines**:

```powershell
$TaskDescription = ""
$descLines = @()
foreach ($line in ($TaskBlock -split '\r?\n')) {
    if ($line -match '^\s*- (.+)$' -and $line -notmatch '^\s*- tags:') {
        $descLines += $Matches[1].Trim()
    }
}
if ($descLines.Count -gt 0) {
    $TaskDescription = $descLines -join "`n"
}
```

The new `tasks.md` format uses prose paragraphs, not bullets. Consequence: `$descLines` is empty, `$TaskDescription` stays empty, and line 156 falls through to `$rawSummary = $TaskTitle`. That `$rawSummary` then flows into both the handoff file body (line 173) AND the `task_description:` field in the spawned worktree's `_millhouse/task/status.md` (line 303).

So the bug affects two artifacts, not just the handoff:

1. `_millhouse/handoff.md` — empty body
2. `_millhouse/task/status.md` `task_description:` — empty (just the title)

This is a long-standing parser bug that wasn't caught before because the older `tasks.md` entries either had bullets in their descriptions or were short enough that "title only" felt sufficient. The new concise format exposes it.

#### Fix

Replace the bullet-only matching loop with one that captures all non-blank, non-heading lines from the task block (between the `## [>] <title>` heading and the next `## ` heading or EOF). Optionally stop at the first blank line if you want a short summary, or include all paragraphs for a full description.

A reasonable shape:

```powershell
$TaskDescription = ""
$descLines = @()
$inDescription = $false
foreach ($line in ($TaskBlock -split '\r?\n')) {
    # Skip the heading itself
    if ($line -match '^## ') {
        $inDescription = $true
        continue
    }
    if (-not $inDescription) { continue }

    # Stop at next heading
    if ($line -match '^## ') { break }

    # Skip blank lines at the very start; keep them once content begins
    if ($descLines.Count -eq 0 -and $line.Trim() -eq '') { continue }

    $descLines += $line
}
# Trim trailing blank lines
while ($descLines.Count -gt 0 -and $descLines[-1].Trim() -eq '') {
    $descLines = $descLines[0..($descLines.Count - 2)]
}
if ($descLines.Count -gt 0) {
    $TaskDescription = ($descLines -join "`n").Trim()
}
```

Approximately 10 lines of changed PowerShell. The fix is straightforward; the diagnosis was the hard part.

#### Connection to the other fixes

This one is independent of the autonomous-fix policy and the worktree-isolation rule. It's bundled into Proposal 02 because Proposal 02 is explicitly the "small surgical fixes" home, not because the three fixes are technically related. They share a common shape: small, surgical, survives the larger architecture rewrite.

## Goals

- Add `[autonomous-fix]` commit tagging requirement to the orchestrator brief (current and future).
- Add `autonomous_fixes` array to the orchestrator's final JSON contract.
- Update mill-go's completion notification to relay the count and SHAs of any autonomous fixes.
- Add the worktree-isolation rule to `conversation/SKILL.md`.
- Audit existing skills for parent-side writes that aren't legitimately in mill-merge / mill-cleanup territory; fix anything found.
- Rewrite `mill-spawn.ps1`'s task-description parser to capture prose paragraphs, not just bullet-point lines. Verify both `handoff.md` and the spawned worktree's `task/status.md` carry the description correctly.

## Non-goals

- Implementing the stronger version of the autonomous-fix policy (justification file, hard cap, scope limit). Wait until the minimum version proves insufficient.
- Rewriting mill-go's overall flow. That's Proposal 04+05.
- Adding similar policies to other skills (mill-start, mill-cleanup, etc.) — only the orchestrator and implementer can self-modify code mid-run.

## Open questions for the discussion phase

1. Is the `[autonomous-fix]` prefix sufficient, or should there also be a Git trailer (`Autonomous-Fix: true`) for tooling that grep's commit bodies, not just subjects?
2. Should the orchestrator also write a brief one-line note about each autonomous fix into `_millhouse/task/status.md` (e.g. as a `autonomous_fix_<n>:` field), so the live status reflects them in real time, not just at end-of-run?
3. The worktree-isolation rule needs an explicit "exception" for mill-merge and mill-cleanup. Should those exceptions be in the rule itself ("...except mill-merge and mill-cleanup, which need to operate on the parent's merge state"), or should those skills explicitly opt in via a comment that acknowledges they're an exception?

## Acceptance criteria

- The implementer-brief template (current Sonnet version, in `plugins/mill/doc/modules/implementer-brief.md`) has a section explaining when autonomous fixes are allowed and the tagging requirement.
- A test run that triggers an autonomous fix (e.g. inject a known-broken `spawn-agent.ps1` quirk) produces a commit with `[autonomous-fix]` in the subject and a final JSON line containing that commit's SHA.
- `conversation/SKILL.md` has a "Worktree isolation" section; running a session from a child worktree and asking the agent to commit a parent-side change produces a refusal with reference to the rule.
- Grep across `plugins/mill/skills/` finds zero `cd <parent>` patterns and zero parent-side `git add/commit/push` outside of mill-merge and mill-cleanup.
- `mill-spawn.ps1` invoked on a `tasks.md` entry with a prose-paragraph description (no bullets) produces a `_millhouse/handoff.md` whose `## Discussion Summary` section contains the actual prose, and a `_millhouse/task/status.md` whose `task_description:` field also contains the actual prose. Backward-compatible: bullet-only descriptions still work.

## Risks and mitigations

- **Models ignore the commit tag rule** if the brief language is weak. Mitigation: same lesson as bug 3 from the previous run — make it load-bearing, with a stated consequence and a "before X you must Y" precondition format.
- **Worktree-isolation rule is too strict for legitimate use cases.** Mitigation: explicit exceptions for mill-merge/mill-cleanup, documented in both the rule and the affected skills.
- **Audit misses something.** Mitigation: the audit is small (≤10 skill files) and the grep pattern is unambiguous.
- **Parser fix breaks bullet-format backward compatibility.** Mitigation: the new parser keeps the same fall-through ("if there are no description lines, fall back to title") and treats bullet lines the same as prose lines (a `- foo` line just becomes a description line that happens to start with `- `). Old tasks.md entries continue to work; only the extracted text differs slightly (bullets included rather than stripped).

## Dependencies

- None. This proposal can ship before, after, or in parallel with any other proposal.
- After Proposal 05 lands, the autonomous-fix policy needs to be re-applied to the new Opus orchestrator brief — but the *content* of the policy is the same.
