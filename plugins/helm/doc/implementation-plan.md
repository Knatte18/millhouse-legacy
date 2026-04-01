# Helm — Implementation Plan

Build order based on dependencies. Each phase produces a testable artifact. Do not start the next phase until the current one works.

## Phase 1: Foundation (no dependencies)

### 1.1 Plugin skeleton
- Create `plugins/helm/.claude-plugin/plugin.json`
- Create `plugins/helm/settings.json` with permissions: `Skill(helm:*)`, `SlashCommand(/helm:*)` (Bash, Agent, etc. are already allowed by CC's default permissions)
- Create skill directory stubs
- Add to `marketplace.json`

**Test:** Plugin installs without errors.

### 1.2 helm-receiving-review
- Standalone skill extracted from reviews.md
- No dependencies on other Helm skills
- Used by both helm-start (plan review) and helm-go (code review)

**Test:** Invoke the skill manually, verify decision tree loads into context.

### 1.3 helm-setup
- Depends on: plugin skeleton
- Implements: kanban.md "Setup" section (9 steps)
- Creates: `_helm/config.yaml`, `_helm/knowledge/`, `_helm/scratch/`, `.gitignore` entry
- Requires: `gh` CLI authenticated

**Test:** Run on a real repo. Verify GitHub Project board created, columns configured, config.yaml populated with all IDs.

### 1.4 helm-add
- Depends on: helm-setup (needs config.yaml for project IDs)
- Simple one-shot: parse title/body, create issue, add to board

**Test:** Run helm-add, verify issue appears on board in Backlog column.

---

## Phase 2: Design phase (depends on Phase 1)

### 2.1 helm-start (no worktree)
- Depends on: helm-setup (reads board), helm-receiving-review (plan review loop)
- Most complex interactive skill
- Implements: skills.md helm-start flow (steps 0-8)
- Key parts to build in order:
  1. Task selection from board (step 0-1)
  2. Explore + codeguide integration (step 3)
  3. Discussion loop (step 4-5)
  4. Plan writing (step 6) — needs plan format from plans.md
  5. Plan review loop with plan-reviewer agent (step 7)
  6. Plan locking and status.md writing (step 8)

### 2.2 Plan reviewer agent
- Depends on: helm-receiving-review
- Agent definition from reviews.md "Plan Reviewer" section
- Spawned by helm-start during plan review loop

**Test:** Run helm-start on a real task. Discuss, produce a plan, run plan review, approve. Verify `approved: true` in frontmatter and plan path in status.md.

---

## Phase 3: Execution phase (depends on Phase 2)

### 3.1 helm-go (core)
- Depends on: helm-start (approved plan), helm-receiving-review (code review)
- Build in order:
  1. Resume protocol (check git log for existing commits)
  2. Plan reading + staleness check
  3. Test baseline capture
  4. Per-step execution loop (TDD enforcement, systematic debugging on failure)
  5. Per-step commits
  6. Full verification after all steps

### 3.2 Code reviewer agent
- Depends on: helm-receiving-review
- Agent definition from reviews.md "Code Reviewer" section
- Receives diff, plan, codeguide Overview
- Spawned by helm-go after verification

### 3.3 helm-go (post-loop)
- Depends on: 3.1 + 3.2
- Codeguide update, knowledge writing, decisions register, post-review commit
- Kanban updates, completion flow

**Test:** Run helm-go on an approved plan. Verify: all steps execute, per-step commits, code review passes, knowledge written, kanban updated. Test resume by killing helm-go mid-execution and restarting.

---

## Phase 4: Commit and lifecycle (depends on Phase 3)

### 4.1 helm-commit
- No hard dependencies (can be built anytime)
- Mirrors mill-commit: lint, codeguide-update, explicit staging, push
- Useful for ad-hoc commits outside helm-go

### 4.2 helm-status
- Depends on: status.md format being stable (Phase 3)
- Read-only: `git worktree list` + read each status.md + query kanban board

**Test:** Run helm-status with one active worktree. Verify output matches actual state.

---

## Phase 5: Worktrees (depends on Phase 3)

### 5.1 helm-start -w (worktree mode)
- Depends on: helm-start (Phase 2), helm-go working
- Adds: worktree creation, env symlinking, brief writing, VS Code launch
- Worktree branch naming from config.yaml template

### 5.2 helm-merge
- Depends on: helm-start -w (needs a worktree to merge)
- Implements: merge.md full flow
- Key parts:
  1. Checkpoint branch
  2. Merge parent into worktree
  3. Conflict resolution
  4. Verification
  5. Codeguide update (checkpoint diff)
  6. Merge to parent (or PR for main)
  7. Merge locking (parent path resolution)
  8. Cleanup

### 5.3 helm-abandon
- Depends on: worktree exists
- Simple: safety checks, worktree remove, branch delete, kanban update

**Test:** Full cycle: helm-start -w → helm-start in worktree → helm-go → helm-merge back. Test recursive worktrees (worktree from worktree). Test helm-abandon.

---

## Phase 6: Polish (depends on Phase 5)

### 6.1 Notifications (Slack + toast)
- Hook into helm-go's escalation paths and completion flow
- Platform detection for toast

### 6.2 Knowledge synthesis
- Trigger when >5 entries in `_helm/knowledge/`
- Deduplicate, resolve conflicts, write summary

---

## Minimum Viable Helm

**Phase 1 + 2 + 3 + 4.1** = full design → execute → commit cycle without worktrees.

Skills: `helm-setup`, `helm-add`, `helm-start`, `helm-receiving-review`, `helm-go`, `helm-commit`.

This is enough to replace Taskmill for single-stream work. Worktrees (Phase 5) add parallelism but aren't required.
