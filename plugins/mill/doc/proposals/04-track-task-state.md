# Proposal 02 — Track Task State Across Machines (Invert `.millhouse/` gitignore)

**Status:** Needs design — do not start implementation until the open questions below are answered.
**Task entry:** `tasks.md` → "[P3] Track task state across machines — needs design before implementation".
**Depends on:** none
**Blocks:** none
**Priority:** Medium — quality-of-life for multi-machine work; not blocking any other proposal.

## Plan-format v2 note

This document was drafted when plans lived at `.millhouse/task/plan.md` (single file). The `tasks.md` "Plan-format v2" entry introduces a `.millhouse/task/plan/` directory with one overview file plus per-batch files. When this proposal leaves needs-design and becomes an implementation task, every reference to `task/plan.md` below should be re-read as "the `task/plan/` directory's contents" — the autocommit logic applies the same way, just to a tree of files instead of one file.

## Empirical motivation from the millpy task (2026-04-14)

During the Python toolkit migration, Step 33 tried to bundle `.millhouse/config.yaml` into an atomic commit that also flipped the reviewer pipeline from the old shim to the new `millpy` entrypoints. The commit landed but the config file was silently dropped because the path is gitignored. The task's acceptance criteria listed "config switched over" as done; the config actually moved only in the local working tree, and any fresh clone would start from the old shim state.

This is a direct, reproduced instance of the "gitignore rule broader than its semantic justification" argument below. Task-state and config live at the wrong semantic layer for the current rule.

## One-line summary

Invert the `.millhouse/` gitignore rule so the **task-level and repo-level** state (`config.yaml`, `task/discussion.md`, `task/plan.md`, `task/status.md`, `task/reviews/`) is tracked by git, while only the genuinely ephemeral and machine-specific pieces (`scratch/`, `children/`, `handoff.md`, `task/implementer-brief-instance.md`) stay ignored. The durable artifacts that make a Mill task meaningful travel with the branch — continuing a task on a different machine stops being impossible.

## Background

`.millhouse/` was designed as a per-machine blob: config.yaml (per-worktree git settings), scratch/ (ephemeral), children/ (parent worktree registry), forwarding `*.ps1` wrappers, handoff.md (one-shot). All of that is correctly gitignored. Then task state (`discussion.md`, `plan.md`, `status.md`, `reviews/*.md`) got dumped into the same directory during early build-out — and it has **completely different semantics**. It is per-task, repo-level, durable, and it is the single most valuable runtime output of mill-start / mill-go outside of the code itself.

The mismatch surfaces in one very concrete way: **you cannot continue a task on another machine.** On machine A you run `mill-start`, discuss, write the plan, run plan-review, push the branch, and go home. On machine B you pull the branch, run `mill-go`, and it fails — there is no `.millhouse/task/discussion.md`, no `plan.md`, no `status.md`. The branch has the `[active]` marker in `tasks.md` and nothing else. You either start over (`mill-abandon`, `mill-start` again, throwaway the lost context) or you rsync `.millhouse/` out-of-band.

The root cause is the gitignore rule being **broader than its semantic justification**. `.millhouse/*` as a blanket ignore is too aggressive; only four specific things in that directory are actually machine-specific or ephemeral:

- `.millhouse/scratch/` — ephemeral materialized prompts, parity reports, worker review files
- `.millhouse/children/` — parent worktree's registry of spawned children (only meaningful on the parent)
- `.millhouse/handoff.md` — one-shot brief consumed by mill-start and then deleted
- `.millhouse/task/implementer-brief-instance.md` — per-invocation prompt materialization that rehydrates from `plan.md`

Everything else in `.millhouse/` — `config.yaml`, `task/discussion.md`, `task/plan.md`, `task/status.md`, `task/reviews/*.md` — is repo-level or task-level content that should travel with the branch.

(There is a small machine-specific tail inside `config.yaml` itself — `notifications.slack.webhook`, `notifications.toast.enabled`, and eventually credential-adjacent fields — but these are a minority of the file. The cleaner long-term split is `config.yaml` (tracked) + `config.local.yaml` (ignored, overrides), but that refinement is not required for this proposal to land. See "Future refinement — config split" below.)

The only genuinely per-worktree field in today's config is `git.parent-branch`, and it is set mechanically at spawn time from `git branch --show-current` of the source worktree. It does not require user editing. Long-term, that field could be computed at runtime from `git worktree list --porcelain`, eliminating per-worktree state from config entirely. For this proposal, it is tracked as-is — the value is the parent branch at the moment the worktree was created, and that is a durable fact about the worktree.

## Scope

### Invert the gitignore rule

Current `.gitignore` entry (effectively):

```
.millhouse/
```

New entries:

```
.millhouse/scratch/
.millhouse/children/
.millhouse/handoff.md
.millhouse/task/implementer-brief-instance.md
```

Everything else under `.millhouse/` is tracked. No explicit whitelist; just a narrower ignore.

### Autocommit task-state on phase transitions

Orchestrators (`mill-start`, `mill-go`, `mill-merge`, `mill-abandon`) add a commit step at every phase transition that writes to `.millhouse/task/`:

- `mill-start` after Phase: Discussion File — commit `.millhouse/task/discussion.md` + `.millhouse/task/status.md`
- `mill-start` after Phase: Handoff — commit `.millhouse/task/status.md` (phase: discussed)
- `mill-go` after Phase: Plan — commit `.millhouse/task/plan.md` + `.millhouse/task/status.md` (phase: planned)
- `mill-go` Thread B after each implementation step — commit `.millhouse/task/status.md` (phase: step-N, implementation file changes come in the same commit as the step's functional change)
- After each review round — commit `.millhouse/task/reviews/<round>.md` + `.millhouse/task/status.md`
- `mill-merge` — delete `.millhouse/task/` before merge, commit the deletion, then merge

Commit message convention: `task: phase <phase-name>` or `task: phase <phase-name> step <N>`, so the generated commits are easy to filter in `git log` views (`git log --invert-grep --grep='^task:'` hides them).

### Merge handling

`mill-merge` runs `git rm -r .millhouse/task/ && git commit -m "task: cleanup for merge"` as the last step before the actual merge. The merge to the parent branch has no task-state residue — `main` stays clean, and the feature-branch history shows the task-state arc up to the cleanup commit. A squash merge on the parent collapses the task-state commits into the single squashed commit, which doesn't land on the parent's working tree because the cleanup commit came first.

### Parent worktree's own active task

The parent worktree (e.g. `millhouse/main`) typically has its own active task in `.millhouse/task/` at any moment. When a child worktree is spawned, mill-spawn copies `.millhouse/` from parent to child (excluding `task/`, `scratch/`, `children/`). The parent's task-state lives on the parent's branch; the child's task-state lives on the child's branch; they never collide because they're committed to different branches.

### Concurrent work from two machines

If machine A and machine B both check out the same feature branch and both run `mill-go`, the first one to commit `.millhouse/task/status.md` wins. The second one's push fails with a non-fast-forward error. The orchestrator runs `git pull --ff-only` before each phase transition; if it fails, abort with "another machine has made progress on this branch — pull and restart".

This is correct behavior. Two parallel mill-go runs on the same task is not a supported mode.

### Cross-machine continuation flow

Machine A:
1. `mill-start` → discussion.md written and committed (`task: phase discussed`)
2. `mill-go` → plan.md written and committed (`task: phase planned`)
3. `git push origin feature-branch`
4. Quit

Machine B:
1. `git fetch && git checkout feature-branch`
2. `.millhouse/task/` is populated from the fetched commits — discussion.md, plan.md, status.md, reviews/ all present
3. `mill-go` → sees `phase: planned` in status.md, resumes implementation
4. Continues as if machine A's session never ended

## Non-goals

- Splitting `config.yaml` into `config.yaml` + `config.local.yaml` for the machine-specific tail. That is a future refinement (see "Future refinement — config split" below); this proposal ships without it, accepting that a few machine-specific fields (`notifications.slack.webhook`, `notifications.toast.enabled`) will be tracked alongside the repo-level fields. The user can leave them blank per machine or override via env vars.
- Moving task state out of `.millhouse/` entirely into a top-level `mill/` directory. That is cleaner semantically but requires rewriting every skill doc, every PS1 / Python reference, and mental-model-retraining. Inverting the gitignore rule achieves the same cross-machine property with zero skill-doc churn.
- Automatic merge-conflict resolution on `.millhouse/task/status.md`. The conflicting-machine case aborts with a clear error; the user resolves.
- History scrubbing of review files that contain code snippets. Review files land on the feature branch as-is. For private repos (the current case) this is fine. For public repos, a future variant could selectively omit `reviews/` from the tracked set.
- Migrating existing in-flight tasks across machines. This proposal changes the rule forward — existing task state on one machine stays on that machine and doesn't retroactively appear on other machines.

## Decisions to resolve during the discussion phase

1. **Commit granularity.** Autocommit at every phase transition, or only at "interesting" transitions (`discussed`, `planned`, `implementing`, `complete`, `abandoned`)? Finer granularity preserves timeline fidelity; coarser granularity reduces commit churn.
2. **Commit-message prefix.** `task:` or `mill:` or something else? `task:` matches the existing `task: claim <title>` / `task: cleanup <title>` convention used by mill-spawn and mill-merge. Recommended.
3. **Pull-before-commit policy.** Always `git pull --ff-only` before a task-state commit? Or pull at session start only? Always is safer; only-at-start is faster.
4. **Behavior when autocommit hits a dirty working tree.** If the user has uncommitted changes in their code while mill-go tries to commit `.millhouse/task/status.md`, the mill-go commit should stage ONLY `.millhouse/task/`, never mix with the user's in-progress edits.
5. **`implementer-brief-instance.md` — tracked or ignored?** It is a per-invocation materialized prompt, rehydrated from `plan.md`. Ignored by default (machine B can rehydrate on demand). Confirm.
6. **Does `mill-abandon` commit the abandon decision before deletion?** Probably yes — `task: phase abandoned` commit, then `.millhouse/task/` deletion commit, so the abandon is visible in history.
7. **Interaction with `mill-setup`.** `mill-setup` writes forwarding wrappers to `.millhouse/*.ps1`. Those wrappers are per-repo-clone (they reference the plugin cache path). Are they tracked (repo-level) or ignored (per-machine)? Probably ignored — plugin cache paths differ per machine. Clarify the full `.millhouse/` inventory for machine-vs-repo classification as part of the discussion.

## Acceptance criteria

- `.gitignore` narrows from `.millhouse/` to the four explicit ignore patterns above.
- Every phase transition in `mill-start`, `mill-go`, `mill-merge`, `mill-abandon` ends with a `git commit` of `.millhouse/task/` with a `task:`-prefixed message.
- `mill-merge` deletes `.millhouse/task/` before merging. The merge into the parent branch has no task-state residue.
- On a fresh clone of a feature branch mid-task, `mill-go` runs successfully against the committed task state without needing any external sync.
- Two machines racing on the same branch surface a non-fast-forward error and refuse to proceed until the user resolves.
- The existing parent worktree's own active task state is not disturbed.
- Skill docs that reference `.millhouse/task/*.md` paths keep working unchanged — the paths didn't move, only the gitignore rule changed.
- mill-spawn's existing behavior of copying `.millhouse/` from parent to child continues to exclude `task/`, `scratch/`, and `children/` (the child starts fresh).

## Risks and mitigations

- **Commit noise on the feature branch.** 5-20 task-state commits per task, on top of the actual implementation commits. Mitigation: standard `task:` prefix means `git log --invert-grep --grep='^task:'` hides them. Squash merge on the parent collapses them into the merge commit.
- **Review files contain source snippets.** They land in the branch history. For this repo that is fine. For public repos, future variants could omit `reviews/`.
- **Two-machine races.** Handled by `git pull --ff-only` guard before each task-state commit. User resolves.
- **Merge conflict on `status.md` between concurrent worktrees of the same repo.** Parent and child have separate branches — no conflict. If the user manually checks out the same branch in two different local worktrees and runs mill-go in both, they'll race per the two-machine case. Same handling.
- **`.millhouse/config.yaml` now tracked and contains machine-specific tail.** For this proposal's scope, we accept that `notifications.slack.webhook` etc. are tracked as empty strings by default. A future proposal splits `config.yaml` + `config.local.yaml`. Until then, users either leave the tail blank or override via env vars.
- **`mill-setup`-generated forwarding wrappers are per-machine.** If they are in `.millhouse/` they get tracked unless explicitly ignored. Add them to the ignore list: `.millhouse/*.ps1` or similar. Scope during discussion.
- **Existing worktrees' `.millhouse/task/` content is not in git history.** When this proposal lands, existing in-flight tasks on other machines stay siloed. Forward-going tasks are portable; backward compat is "throw one away".
- **Autocommit running in the middle of a user's own editing session.** The autocommit stages ONLY `.millhouse/task/` paths. Any mixed user changes stay in the working tree untouched. Mitigation: explicit `git add .millhouse/task/` (no blanket `git add -A`) in every orchestrator commit step.

## Dependencies

- None.
- The Python toolkit task (completed 2026-04-14 on branch `python-toolkit--reti`) moved the reviewer pipeline into `millpy` but did not change gitignore semantics. This proposal is orthogonal — it changes the gitignore rule and adds autocommit hooks in orchestrator skills. It builds on the `millpy` modules but does not block them.

## Future refinement — config split

If `config.yaml`'s machine-specific tail becomes annoying (blank slack-webhook committed to main, per-machine toast preferences fighting), a follow-up proposal can split it:

- `.millhouse/config.yaml` — tracked, repo-level: `git`, `repo`, `reviews`, `models`, `review-modules`
- `.millhouse/config.local.yaml` — ignored, machine-level: `notifications`, any credential-adjacent fields, any per-machine overrides of repo defaults

The `millpy.core.config` loader reads both and merges (local overrides repo). This is a standard pattern (VSCode workspace vs user settings, git `.git/config` vs `~/.gitconfig`). Not required for this proposal to land.

## Rename possibility (long-term, non-blocking)

This proposal was superseded by the `.millhouse/` unified layout. Task state now lives in the wiki via `.millhouse/wiki/active/<slug>/`, which travels with the wiki git push/pull — achieving the cross-machine portability goal through a different mechanism (wiki-based shared state) rather than tracking task state on the feature branch.
