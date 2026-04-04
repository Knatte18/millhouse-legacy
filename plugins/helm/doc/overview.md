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

The `kanbans/` directory contains 4 separate board files (`backlog.kanban.md`, `processing.kanban.md`, `done.kanban.md`, `blocked.kanban.md`), each a standalone kanban board recognized by the VS Code kanban.md extension. Tasks are `###` headings moved between files as work progresses. GitHub sync is available on demand via `helm-sync`. Details in [kanban-format.md](modules/kanban-format.md).

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
| `helm-add` | Create a new task on the kanban board | One-shot |
| `helm-merge` | Merge worktree back to parent | Semi-autonomous |
| `helm-status` | Dashboard of all worktrees | Read-only |
| `helm-abandon` | Discard a worktree, move task back to Backlog | Interactive |
| `helm-sync` | Sync local kanban board to GitHub Projects | One-shot |
| `git:git-commit` | Ad-hoc commit (general git skill, not Helm-specific) | One-shot |

Each skill is defined in `plugins/helm/skills/<name>/SKILL.md`.

## Document Index

| File | Contents |
|------|----------|
| [overview.md](overview.md) | This file — architecture and principles |
| [modules/worktrees.md](modules/worktrees.md) | Worktree model, lifecycle, nesting, env setup |
| [modules/plans.md](modules/plans.md) | Plan format, locking, staleness detection |
| [modules/kanban-format.md](modules/kanban-format.md) | kanban.md file format reference |
| [modules/knowledge.md](modules/knowledge.md) | Knowledge curation between tasks |
| [modules/coherence.md](modules/coherence.md) | Why Helm doesn't use coherence audits |
| [modules/codeguide.md](modules/codeguide.md) | Codeguide integration points |
| [modules/constraints.md](modules/constraints.md) | Repo-specific invariants (CONSTRAINTS.md) |
| [modules/validation.md](modules/validation.md) | Post-write validation rules for .kanban.md and config.yaml |
| [decisions.md](decisions.md) | Design decisions and open questions |
