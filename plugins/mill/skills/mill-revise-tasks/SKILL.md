---
name: mill-revise-tasks
description: Drain GitHub issue queue into tasks.md — fetch, status-check, brevity-cleanup of existing tasks, consolidate, propose, then write on user approval.
---

# mill-revise-tasks

You are revising `tasks.md`. Pull open GitHub issues, judge each against the current repo state, propose brevity-cleanup of existing long tasks, consolidate everything into a coherent task list, present a proposal to the user, and on approval write the changes (`tasks.md`, new background docs in `plugins/mill/doc/proposals/`, and close the GitHub issues with comments pointing to the consolidating tasks).

This skill replaces the older `mill-inbox` import flow with a status-checking + brevity-cleanup + consolidation pass.

## Entry checks

1. Verify `gh auth status` succeeds. If not, stop and tell the user:

   > `gh` is not authenticated. Run `gh auth login` and re-invoke `/mill-revise-tasks`.

2. Load `.millhouse/config.yaml`. Resolve tasks.md via `millpy.tasks.tasks_md.resolve_path(cfg)`. If resolution raises, stop and tell the user to run `mill-setup` first. Extract from config:
   - `revise.brevity-threshold-lines` (default `5`)
   - `revise.brevity-threshold-chars` (default `500`)

## Step 1 — Fetch issues

Invoke `fetch_issues.py` as a subprocess, resolving the script via three-tier path resolution:

1. `.millhouse/fetch-issues.py` forwarding wrapper (written by `mill-setup`)
2. `<repo-root>/plugins/mill/scripts/fetch_issues.py` (in-repo plugin source)
3. `~/.claude/plugins/cache/millhouse/mill/<latest-version>/scripts/fetch_issues.py` (plugin cache)

Confirm `.millhouse/scratch/issues.json` was written. Read the JSON and extract:
- `repo`
- `fetchedAt`
- the `issues` array (each entry has at minimum `number`, `title`, `body`, and `labels`)

## Step 2 — Status-check each issue

For each issue in the fetched list:

- Read the title and body.
- Search the repo for evidence the issue is already addressed: grep for keywords from the title in `git log --since=<recent>` (e.g. last 90 days) and in current source files. Also check whether the issue references a removed subsystem or obsolete flow.
- Classify the issue with one of three verdicts:
  - `fixed-in-main` — evidence found in recent commits or current code that the issue is addressed.
  - `moot` — references a removed subsystem or obsolete flow; no longer relevant.
  - `still-open` — neither of the above; needs a task or a fold-into-existing-task.
- Record the verdict and a one-sentence rationale per issue. The user will review these in Step 7 and can override any verdict by editing the proposal file.

## Step 3 — Read existing tasks.md

Parse tasks.md via `tasks_md.parse(tasks_md.resolve_path(cfg))` (config loaded in Entry check 2). For each task:

- Note the marker (none / `[s]` / `[active]` / `[done]` / `[abandoned]`).
- Detect protected status: scan body for the literal HTML comment `<!-- protected -->`. Protected tasks are EXCLUDED from any merge/consolidation; their bodies are also EXCLUDED from brevity-cleanup proposals.
- Compute body line count and char count. If the body exceeds EITHER `brevity-threshold-lines` OR `brevity-threshold-chars` AND the task is not protected, mark it for a brevity-cleanup proposal.

## Step 4 — Consolidation pass

For each `still-open` issue, decide a landing place:

- **Fold into existing task** — if a non-protected task already covers the same scope (LLM judgment), fold the issue by appending its details to that task body OR (more likely) by adding a one-line `Consolidates issue #N` reference. Capture the update in the proposal.
- **Create new task** — if no existing task fits, draft a new task entry. New tasks MUST follow the short format:
  ```markdown
  ## <Title>
  - tags: [<comma-separated tags>]
  - bg-doc: <path>   # optional, only when a background doc is needed
  - <1–2 sentence summary>
  ```
- **Merge with related task** — if two non-protected existing tasks plus the issue all describe overlapping work, propose merging them into one consolidated entry.

Dedup path: if two issues have nearly-identical content, propose folding BOTH into one new or existing task. Deduplication happens here, not at report time.

## Step 5 — Background-doc proposals

For each new or consolidated task, ask whether it needs a background doc in `plugins/mill/doc/proposals/`. Auto-pick the next `NN-` prefix by scanning `plugins/mill/doc/proposals/` for the highest current number and adding 1. The user answers Y/N per task in the proposal-review step.

## Step 6 — Brevity-cleanup proposals

For each existing long task flagged in Step 3, draft a proposed shortening:

1. Extract the long body content into a new bg-doc at `plugins/mill/doc/proposals/NN-<slug>.md` (auto-numbered per Step 5).
2. Replace the task body with:
   - `- tags: [<existing tags>]`
   - `- bg-doc: plugins/mill/doc/proposals/NN-<slug>.md`
   - `- <1–2 sentence summary>` (you draft the summary from the original body)

The user can approve or reject per task in Step 7.

## Step 7 — Write the proposal

Render the consolidated proposal to `.millhouse/scratch/revision-proposal.md` with this structure:

```markdown
# Tasks Revision Proposal

Generated: <UTC timestamp>
Issues fetched: <fetchedAt>
Repo: <repo>

## Issue → Landing Place

| Issue | Title | Verdict | Landing | Rationale |
|---|---|---|---|---|
| #N | <title> | still-open | New task: "<task-title>" | <one-sentence rationale> |
| #N | <title> | fixed-in-main | (drop, close on GH) | <evidence> |
| #N | <title> | moot | (drop, close on GH) | <reason> |
| #N | <title> | still-open | Fold into existing: "<task-title>" | <rationale> |

## New Tasks (drafted)

### "<New Task Title 1>"
- tags: [...]
- bg-doc (proposed): plugins/mill/doc/proposals/NN-<slug>.md (Y/N? — currently: <Y or N>)
- Summary: <2-line summary>
- Sources: issue #N, issue #M

## Brevity Cleanup (existing long tasks)

### "<Existing Task Title>" (current length: <N> lines, <M> chars; threshold: <L>/<C>)
- Proposed bg-doc: plugins/mill/doc/proposals/NN-<slug>.md
- Replacement body:
  - tags: [...]
  - bg-doc: <path>
  - <2-line summary>
- Approve / Reject?

## To Close on GH (with comment)

| Issue | Reason | Comment to post |
|---|---|---|
| #N | fixed-in-main | "Fixed in main as of <commit>: <ref>" |
| #N | moot | "<reason>" |
| #N | folded into "<task-title>" | "Consolidated into task: '<title>'" |

## Approval

Edit this file to override any verdict or proposed change, then return to the chat and confirm with `approve` or `reject`.
```

## Step 8 — Chat summary + path

Print to chat:

- Counts: `<X> issues fetched. <Y> still-open, <Z> fixed-in-main, <W> moot. <V> brevity-cleanup proposals.`
- Path: ``Full proposal at `.millhouse/scratch/revision-proposal.md`. Review and edit, then reply `approve` or `reject`.``

## Step 9 — Wait for user response

Await `approve` or `reject`:

- `reject`: print ``Proposal rejected. No changes made. Proposal kept at `.millhouse/scratch/revision-proposal.md` for re-review.`` Exit.
- `approve`: continue to Step 10.

## Step 10 — Apply changes (on approval)

1. For each new task: append `## <Title>` + body to the in-memory task list.
2. For each folded task: update the existing task body in the in-memory task list.
3. For each brevity-cleanup-approved task: rewrite the existing task body to short form in the in-memory task list.
4. Validate the rendered content via `tasks_md.validate(...)`. If validation fails, ROLL BACK (no writes, no helper calls; exit with error and report to user).
5. **First commit — tasks branch (via helper).** Render the final tasks.md content. Call `millpy.tasks.tasks_md.write_commit_push(cfg, rendered, f"chore: revise tasks.md — {new} new, {folded} folded, {shortened} shortened, {closed} issues closed")`. The helper commits to the tasks branch. If this call fails, do NOT proceed to the feature-branch commit.
6. **Second commit — feature branch (proposal docs only).** For each bg-doc creation: write `plugins/mill/doc/proposals/NN-<slug>.md` with the extracted content. The doc body MUST start with a `# <Title>` h1 matching the task title; subsequent sections may follow the existing `proposals/*` pattern (Context, Decisions, etc.) — but a minimal one-section doc is acceptable when the source content is short. Run `git add plugins/mill/doc/proposals/`. If at least one doc was written, commit with `git commit -m "docs(proposals): add <background-doc-list>"`. Push to the feature branch.
7. For each issue in the "To Close on GH" table: run `gh issue close <N> --repo <repo> --comment "<comment>"`. Track each close result; if any fail, log the failure but continue with the rest.

## Step 11 — Report

Print to chat:

> Revision applied. `<N>` tasks added, `<M>` folded, `<O>` shortened. `<P>` GH issues closed. `<Q>` bg-docs created.

## Rules

- Never silently rewrite `tasks.md` without the proposal/approval gate.
- Tasks-branch commit always lands before the feature-branch commit. If the tasks-branch commit fails, the feature-branch commit does not run — the content model stays canonical.
- Protected tasks (`<!-- protected -->` in body) are NEVER merged with other tasks and NEVER subject to brevity-cleanup.
- If two issues have nearly-identical content, propose folding them BOTH into one new or existing task — dedup happens here, not at report time.
