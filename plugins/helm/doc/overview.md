# Helm — Overview

Worktree-based task orchestration plugin for Claude Code. Human-in-the-loop design and planning, autonomous execution with self-review.

## Origin

Helm combines ideas from three sources:

- **Taskmill** (millhouse) — changelog, codeguide integration, human-in-the-loop workflow
- **Autoboard** (Willie Tran) — review gates, coherence audits, knowledge curation, quality dimensions, receiving-review protocol
- **Motlin** (Craig Motlin) — plugin structure, skill conventions

## Core Principles

From Autoboard's Toyota-inspired model:

1. **Never let the builder inspect their own work.** Code review is a separate Agent call — the reviewer has no shared context with the implementer.
2. **Stop the line the moment something breaks.** Test failures halt progress. No "fix it later."
3. **Never pass a defect downstream.** Coherence audit after merge. Defects do not propagate to parent branches.

## Architecture Summary

### Worktree Model

All work happens in git worktrees. The repo root stays on `main` and serves as home base for creating new worktrees. Details in [worktrees.md](worktrees.md).

### Task Tracking

GitHub Projects V2 is the single source of truth for tasks. No local backlog files. Issues are cards on a kanban board, moved between columns as work progresses. Details in [kanban.md](kanban.md).

### Execution Model

Two phases with a clean boundary:

| Phase | Mode | Skill | What happens |
|-------|------|-------|-------------|
| **Design** | Interactive | `helm-start` | Pick task, discuss, clarify, plan, review plan with user |
| **Execute** | Autonomous | `helm-go` | Implement, test, code-review (agent-to-agent), commit |

The user controls the transition. `helm-go` never asks for input during normal operation.

### Skills Overview

| Skill | Purpose | Mode |
|-------|---------|------|
| `helm-start` | Pick task, discuss, plan, review plan | Interactive |
| `helm-start -w` | Same, but spawns worktree + VS Code first | Interactive |
| `helm-go` | Implement, test, code-review, commit | Autonomous |
| `helm-add` | Create a new task (GitHub issue + board) | One-shot |
| `helm-merge` | Merge worktree back to parent | Semi-autonomous |
| `helm-status` | Dashboard of all worktrees | Read-only |
| `helm-abandon` | Discard a worktree, move task back to Backlog | Interactive |
| `helm-commit` | Ad-hoc commit outside helm-go | One-shot |

Details in [skills.md](skills.md).

## Document Index

| File | Contents |
|------|----------|
| [overview.md](overview.md) | This file — architecture and principles |
| [modules/worktrees.md](modules/worktrees.md) | Worktree model, lifecycle, nesting, env setup |
| [modules/skills.md](modules/skills.md) | All skill definitions and flows |
| [modules/plans.md](modules/plans.md) | Plan format, locking, staleness detection |
| [modules/reviews.md](modules/reviews.md) | Plan review, code review, receiving-review protocol |
| [modules/kanban.md](modules/kanban.md) | GitHub Projects V2 integration |
| [modules/knowledge.md](modules/knowledge.md) | Knowledge curation between tasks |
| [modules/coherence.md](modules/coherence.md) | Coherence audits and quality dimensions |
| [modules/merge.md](modules/merge.md) | Merge strategy, checkpoints, locking, PR workflow |
| [modules/notifications.md](modules/notifications.md) | Slack, toast, status files |
| [modules/codeguide.md](modules/codeguide.md) | Codeguide integration points |
| [modules/failures.md](modules/failures.md) | Failure classification and escalation |
| [modules/open-questions.md](modules/open-questions.md) | Resolved and open design decisions |
