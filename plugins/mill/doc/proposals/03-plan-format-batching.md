# Proposal 03 — Plan-Format Batching

**Status:** Proposed
**Depends on:** none
**Blocks:** Proposal 06 (parallelizable batches) requires this as a prerequisite

## One-line summary

Introduce a `## Batch N: <name>` grouping in the plan format so the implementer commits at batch boundaries instead of after every atomic step. Reduces commit noise from ~18 commits per task to ~5, while preserving atomicity for in-flight execution clarity.

## Background

The "Add functionality to track the status of a child worktree from a parent" task (completed 2026-04-13) produced **18 commits** for what was logically ~5 cohesive units of work:

1. Migration step (hardlinks + junction)
2. Validation/format documentation updates
3. Skill rewrites (mill-spawn, mill-start, mill-go, mill-merge, mill-abandon, mill-cleanup, mill-setup, mill-status)
4. Documentation sweep (overview, modules, implementer-brief, conversation)
5. Verification + final fixes

The current `plan-format.md` says each step gets its own commit. That's a one-to-one mapping between atomic step and commit, which makes the implementer's resume-on-crash recovery simple (each commit is a checkpoint) but makes the resulting git history extremely noisy. 18 commits per task is more friction than information — `git log` becomes overwhelming, and a reader trying to understand what changed in a task has to mentally batch the commits anyway.

The wall-clock review cost is **not** affected by commit count — the reviewer reviews the total diff (`git diff <plan_start_hash>..HEAD`), not per-commit. So fewer commits doesn't make review faster. It only makes history nicer.

## What is a batch?

A **batch** is a group of atomic steps in the plan that share a logical theme and ship as a single commit. The plan still lists steps individually for the implementer's internal checkpointing and for clarity during planning, but commits happen at batch boundaries, not step boundaries.

Example structure:

```markdown
## Steps

### Batch 1: Migrate in-flight state

#### Step 1.1: Create _millhouse/task/ directory
- Creates: ...
- Modifies: ...

#### Step 1.2: Hardlink status.md, plan.md, discussion.md, brief
- Creates: ...
- Modifies: ...

#### Step 1.3: Create reviews directory junction
- Creates: ...
- Modifies: ...

**Commit:** `chore: migrate in-flight state to _millhouse/task/`

### Batch 2: Update tasks.md format vocabulary

#### Step 2.1: Edit tasksmd-format.md ...
#### Step 2.2: Edit validation.md ...

**Commit:** `docs: trim tasks.md phase-marker vocabulary`

...
```

The implementer reads each step card individually (preserving the atomicity invariant — each card is still self-contained), implements them in order, and at the end of the batch runs the batch's commit. If a step within a batch fails, the implementer rolls back the staged changes for that batch and surfaces the error.

## Goals

1. Update `plan-format.md` to describe batches as a first-class concept.
2. Define how plan steps are nested under batches in the markdown structure.
3. Update the implementer's brief to commit at batch boundaries, not step boundaries.
4. Define a resume protocol when a crash happens mid-batch.
5. Define how the plan reviewer evaluates batches (at the batch level, the step level, or both).
6. Migrate the existing `plan-review.md` template to understand batches.

## Non-goals

- Parallel batches. Proposal 06 covers that as a follow-on.
- Changing the atomicity invariant. Each step card still has to satisfy the extraction test individually.
- Backporting the batch concept to past tasks (no need — this is a forward-looking change).

## Design decisions

### Decision: Batch boundaries are explicit, not inferred

Each batch is marked with `### Batch N: <name>`. Steps inside a batch are nested under it as `#### Step N.M: <name>`. The implementer commits at the end of the batch, using a `**Commit:**` line at the end of the batch (not the end of each step).

**Why:** Implicit batching (the implementer guesses what to group) is unreliable. Explicit boundaries are unambiguous and reviewable.

**Alternatives rejected:** Inferring batches from `Modifies:` overlap (fragile, hard to explain). Heuristic batching by file count or directory (arbitrary thresholds). One commit per task with no batching at all (loses the resume-on-crash checkpoint property entirely).

### Decision: Resume protocol is "redo the batch from the start"

If a crash happens mid-batch (e.g. step 3.2 of 5 in batch 3), the implementer on resume detects no commit for batch 3, discards any uncommitted/staged changes, and re-runs all of batch 3 from step 3.1.

**Why:** Step-level resume tracking adds complexity and persistence requirements (where do you store "completed step 3.1, started step 3.2"?). Re-running the whole batch is acceptable because step cards are designed to be **idempotent** — re-running a step that was partially done should produce the same end state. The atomicity invariant + verbose-is-feature philosophy already encourages idempotent step descriptions.

**Alternatives rejected:**
- Per-step persistence (status.md or a sidecar file) — adds writes, adds drift bugs, adds complexity. Same problem as the current `current_step` issue.
- Cherry-pick partial work forward — fragile, can leave the working tree in a half-state.
- Commit per step regardless of batch (defeats the whole purpose).

### Decision: Plan-reviewer reviews at the step level (unchanged), commits-at-the-batch-level is informational

The plan-reviewer continues to evaluate each step card for atomicity and clarity. The batch grouping is a metadata layer for the implementer; reviewers care about whether each step is independently implementable.

**Why:** Atomicity of step cards is the core quality property. Batching is a packaging concern, not a quality concern.

**Alternatives rejected:** Reviewing batches as units (loses fine-grained feedback). Reviewing both (duplicative).

### Decision: A batch must contain at least 1 step and at most ~6

**Why:** A 1-step batch is fine — it just means that step is self-contained enough to ship alone. A 10-step batch is suspicious — too many disparate operations in one commit makes git history hard to bisect.

**Alternatives rejected:** No upper limit (allows abuse). Hard upper limit of 3 (too restrictive for legitimate cohesive work like a multi-file rename).

### Decision: The plan can have a special "trailer batch" for verification

Many plans end with a "verification" step (grep sweep, smoke test, manual check) that doesn't produce code changes. This step doesn't need its own commit. It can be a separate batch with no `**Commit:**` line, or marked `**No-commit verification batch.**`

**Why:** Verification work isn't a code change. Don't pollute history with empty commits.

**Alternatives rejected:** Force a commit with an empty diff (ugly). Skip verification batches entirely from the plan format (loses the documentation of what was verified).

## Open questions for the discussion phase

1. **What about TDD steps mid-batch?** A TDD step (RED → GREEN → REFACTOR) traditionally produces multiple commits or at least one commit at GREEN. If TDD steps are inside a batch, do they still commit at GREEN, or do they wait for batch boundary? Probably wait for batch boundary, but the brief language needs to be explicit.
2. **Should batches have a `Why:` field** documenting why these specific steps are grouped? Probably yes, for the reviewer's benefit. Adds 1-2 lines per batch.
3. **What about steps that span multiple batches conceptually** (e.g. a step that modifies a file the next batch will also modify)? The atomicity invariant says this is fine — each step is independently implementable. Batching doesn't change that.
4. **How does the implementer's status.md updating work with batches?** Today, `current_step: N` tracks the linear step number. With batches, do we have `current_batch: N, current_step_in_batch: M`, or just `current_step: N.M`? The latter is simpler and matches the markdown structure. (Note: the current_step skip bug from the previous run still needs fixing in the brief — see Proposal 02 for the Why.)
5. **Should mill-status display batch progress** ("Batch 3 of 5: in progress, step 2 of 4") instead of step progress? Probably yes, but this is a mill-status enhancement, not part of the core change.

## Acceptance criteria

- `plan-format.md` describes batches with examples.
- A test plan with 3 batches × 3 steps successfully executes via Thread B with exactly 3 commits, one per batch.
- A simulated crash after batch 2 step 2 successfully resumes by re-running batch 2 from the start, producing the same final commit SHA as a non-interrupted run.
- The plan reviewer evaluates step cards individually (unchanged from today), and produces feedback at the step level.
- Existing plans (which lack batches) are still parseable — the format is backward-compatible by treating each `### Step N` as its own one-step batch.

## Risks and mitigations

- **Implementer skips the batch boundary** and commits per step anyway (same failure mode as the `current_step` skip bug). Mitigation: same lesson — make the batch boundary load-bearing in the brief, with a precondition format and a stated consequence.
- **Resume bug eats partial work** if "re-do the batch" doesn't actually clean the staging area first. Mitigation: explicit `git reset --hard <plan_start_hash_or_last_committed_sha>` at batch start during resume.
- **Plan-reviewer gets confused by the new structure.** Mitigation: update the plan-review prompt template explicitly to acknowledge batches as a metadata layer that doesn't affect atomicity evaluation.

## Dependencies

- None. Can ship independently.
- Proposal 06 (parallelizable batches) requires this as a foundation — parallel batches don't make sense without the batch concept first.
- After Proposal 05 (dual-Opus orchestrator), the implementer subprocess (Sonnet/Haiku) does the per-batch commit. The batch concept moves cleanly into the new orchestrator-implementer split.
