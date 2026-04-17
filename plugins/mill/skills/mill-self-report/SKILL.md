---
name: mill-self-report
description: Reflect on session activity and file detected bugs as GitHub issues. Auto-invoked by mill-plan/mill-go at end-of-work; can also be invoked manually.
argument-hint: "[free-text steering]"
---

# mill-self-report

You are reflecting on the work session that just ended (or that you are currently in). Your job: scan your session context for clear bugs in mill tooling — failures, prompt mismatches, tool errors, surprising behavior — distill them into focused bug candidates, present a numbered list to the user, and file the user's selections as GitHub issues via the `millhouse-issue` skill. Be specific and reproducible: each candidate should name the affected component, what went wrong, and (when possible) why.

## 1. Entry checks

Verify `gh auth status` succeeds. If `gh` is not installed or not authenticated, stop early and tell the user:

> `gh` is not authenticated. Run `gh auth login` and re-invoke `/mill-self-report`. (Skipping bug-filing for this run.)

Exit cleanly. This check fires for BOTH manual and auto-fire invocations — the underlying `gh issue create` would fail without auth in either case, and an explicit early message is clearer than letting `millhouse-issue` fall back to a browser URL silently.

## 2. Invocation modes

- **Auto-fire from `mill-plan` and `mill-go`:** they invoke this skill at end-of-work IF `notifications.auto-report.enabled: true` in `_millhouse/config.yaml`. The skill receives no argument in this mode.
- **Manual:** the user invokes `/mill-self-report` directly.
  - With NO argument, reflect on the current session's events broadly.
  - With a free-text argument (e.g. `/mill-self-report "the Gemini reviewer hung on card 5"`), use the argument as a steering hint focusing the reflection on the topic mentioned.
- The `notifications.auto-report.enabled` config toggle does NOT gate manual invocation — manual always works (subject to the entry check above).

## 3. Step 1 — Reflect on session context

Scan your session memory for:

- Tool failures or unexpected errors during the session.
- Reviewer verdicts that were `UNKNOWN`, halted, or otherwise anomalous.
- Prompt template mismatches (e.g. a tool-use prompt sent to a bulk-mode worker).
- Skill instructions that were unclear, contradictory, or led you astray.
- Subprocess hangs, timeouts, or quota errors.
- Any "this should not have happened" moments related to mill tooling itself (NOT user code being implemented — those are not bugs in mill).

If a free-text steering argument was given, focus your scan on related events.

## 4. Step 2 — Distill into candidates

For each genuine bug observation, produce a focused candidate with:

- **Title** (one line, ≤80 chars, the form `<component>: <what failed>` — e.g. `spawn_reviewer: UNKNOWN verdict on bulk dispatch with tool-use prompt`).
- **Body** (3–6 lines: what happened, where, reproduction hint, observed behavior vs. expected).

Drop transient frustrations, one-offs that have no reproducer, and meta-issues (e.g. "I felt the discussion was long" — not a bug).

## 5. Step 3 — Empty-list short-circuit

If no candidates are produced after distillation, print:

```
No bug candidates from this session.
```

Then exit silently — no toast, no Slack ping, no GH issue, no prompt.

## 6. Step 4 — Present numbered list

Print the candidates as a numbered text list per `mill:conversation` rules (no `AskUserQuestion`):

```
1) <title-1>
   <body-1 first line>
2) <title-2>
   <body-2 first line>
```

Followed by:

> Type comma-separated numbers to file (e.g. `1, 3`), `all` to file every candidate, or `none` to skip.

## 7. Step 5 — File selected candidates

For each selected candidate, invoke the `millhouse-issue` skill via the Skill tool, passing the candidate's title as the slash-command argument. The body is constructed by `millhouse-issue` from the title plus the auto-collected context (origin, branch, timestamp).

For richer body content, this skill MAY pre-write the candidate body to `_millhouse/scratch/self-report-body-<slug>.md` and reference it from the `/millhouse-issue` invocation if needed — but the simpler approach (title-only invocation, let `millhouse-issue` auto-build the body) is the default.

## 8. Step 6 — Report

After all selected candidates are filed (or zero filed), print a one-line summary:

```
Filed N issues: <comma-separated titles>
```

Or:

```
Filed 0 issues.
```

## Rules

- Never invent bugs that didn't actually happen in this session — when in doubt, leave it off the list.
- Bugs are about MILL TOOLING, not about the implementation work the user asked for. A failing test in user code is NOT a mill bug; a failing reviewer subprocess IS.
- Auth is checked at entry (Section 1). The `millhouse-issue` skill itself does NOT check auth — its `gh issue create` invocation falls back to a browser URL on failure — but this skill stops early when unauthenticated for clearer signal in the auto-fire path.
