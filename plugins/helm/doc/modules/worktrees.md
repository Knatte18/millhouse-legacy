# Worktrees

## Model

All work happens in git worktrees. The repo root stays on `main` (or whatever the default branch is) and serves as home base for creating new worktrees.

```
repo root (main) — nobody works here directly
 └── hanf/main (worktree, working base)
      ├── hanf/main/auth (worktree, parent: hanf/main)
      │    ├── tasks executed sequentially
      │    ├── sub-task "OAuth" → user chose worktree
      │    │    └── hanf/main/auth/oauth (worktree, parent: hanf/main/auth)
      │    └── sub-task "session mgmt" → done in this worktree
      ├── hanf/main/csv-export (worktree, parent: hanf/main)
      │    └── tasks executed sequentially
      └── hanf/main/login-bug (worktree, parent: hanf/main)
           └── quick fix, merge back
```

## Key Properties

- **One thread per worktree.** No intra-worktree parallelism. Sequential task execution within each worktree.
- **Cross-worktree parallelism.** Multiple worktrees run in separate VS Code windows with separate CC instances. This is where parallelism lives — not within a worktree.
- **Recursive nesting.** A task in a worktree can spawn a child worktree. Same pattern at every level.
- **Explicit parent.** Every worktree records its `parent_branch`. Merge always goes back to parent.
- **Parent is any branch.** `git worktree add` takes any branch or commit as base. Worktree-from-worktree is natively supported.

## Branch Naming

Worktree branches follow a configurable template. Configured in `_helm/config.yaml` (tracked):

```yaml
worktree:
  branch-template: "{parent-branch}-wt-{slug}"
  path-template: "../{repo-name}-wt-{slug}"
```

Available placeholders:
- `{slug}` — derived from task title (kebab-case, max 20 chars), or user-provided
- `{parent-branch}` — full current branch name (e.g. `hanf/main`)
- `{repo-name}` — basename of the repo root directory (e.g. `py-hanf`)

The `-wt-` separator avoids git ref conflicts — branches with `/` (like `hanf/main`) can't have sub-branches (`hanf/main/slug` would conflict).

Examples:

| Template | Context | Slug | Result |
|----------|---------|------|--------|
| `"{parent-branch}-wt-{slug}"` | branch: `hanf/main`, repo: `py-hanf` | `auth` | branch: `hanf/main-wt-auth` |
| `"../\{repo-name}-wt-{slug}"` | branch: `hanf/main`, repo: `py-hanf` | `auth` | path: `../py-hanf-wt-auth` |

The `path-template` controls where the worktree directory is created on disk. `../` places worktrees as sibling directories to the repo root (e.g. repo at `C:\Code\py-hanf` → worktree at `C:\Code\py-hanf-wt-auth`), not inside the repo.

## When to Use a Worktree

The user always decides. CC never auto-spawns worktrees. Common reasons:

| Situation | Worktree? |
|-----------|-----------|
| CC is busy with another task, you want to start something | Yes |
| Task is large and risky, you want isolation | Yes |
| Hotfix while a feature is in progress | Yes |
| Small task, CC is idle | No — do it in current context |

Use `helm-start -w` to spawn a worktree, or `helm-start` to work in the current context. You can also switch mid-discussion: if you're discussing without a worktree and realize you want one, call `helm-start -w` and CC will write a brief with the discussion so far and spawn the worktree.

## Lifecycle

### Creation

When `helm-start -w` is called:

1. `git worktree add <path> -b <branch-name> <parent-branch>`
2. Symlink gitignored environment files: `for f in .env*; do [ -f "$f" ] && ln -sf "$(pwd)/$f" <worktree-path>/"$f"; done`
3. Create `_helm/` directory structure in worktree (tracked: `knowledge/`, `changelog.md`, `config.yaml`; ignored: `scratch/`)
4. Write `_helm/scratch/briefs/handoff.md` in the child worktree (see [plans.md](plans.md) Handoff Brief Format). If no discussion has happened, populate Discussion Summary from the task title.
5. Ensure the task exists in `.kanban.md` (it should already be there from `helm-add`)
6. `code <worktree-path>` — open VS Code in the new worktree
7. Parent session continues with other work

### Working

User opens CC in the new VS Code window. Runs `helm-start`. CC reads the brief as background context, discusses approach with the user, writes and reviews the plan. After plan approval, user runs `helm-go` for autonomous execution.

### Completion

When all tasks are done, user runs `helm-merge`:
1. Merge parent into worktree (catch up)
2. Verify and audit
3. Merge worktree into parent (or create PR)
4. Cleanup worktree and branch

### Cleanup

```bash
git worktree remove <path>
git branch -D <branch-name>
```

Never cleanup on failure — preserve the worktree for investigation.

## Status Tracking

Each worktree writes `_helm/scratch/status.md`, updated after every step (not just on errors). Canonical format defined in `helm-go` SKILL.md. Key fields:

```markdown
parent: feature/auth
phase: implementing
issue: #57
plan: _helm/scratch/plans/2026-04-01-120000-oauth.md
plan_start_hash: abc123
current_step: 3
current_step_name: Add callback endpoint
tasks_total: 3
tasks_done: 1
steps_total: 5
steps_done: 2
blocked: false
retries:
  step_3: 1
last_updated: 2026-04-01T14:30:00Z
```

`helm-status` reads these files via paths from `git worktree list`. `helm-go` uses `plan:` and `plan_start_hash:` for resume.

## Environment Setup

Git worktrees don't include gitignored files. On creation, symlink:
- `.env`, `.env.local`, `.env.*` — environment variables
- Any other gitignored config files needed for build/test

Dependencies (`node_modules`, `venv`, etc.) must be installed fresh per worktree via the verify command in the plan.
