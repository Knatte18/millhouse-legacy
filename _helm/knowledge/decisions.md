## Separate kanban boards
**Why:** The VS Code kanban.md extension shows each `.kanban.md` file as a separate visual board. Having one board per column gives a cleaner UI with focused views (backlog only, in-progress only, etc.)
**Trade-off:** "Move task" is now a cross-file operation (cut from one file, paste into another) instead of an in-file edit. Slightly more complex for skills, but the mapping from column to file is 1:1 and deterministic.
**Alternatives rejected:** Single file with all columns (original design — visually cluttered), directory of per-task files (too granular, extension doesn't support it well)

## git-pr: always PR, no config flag
**Why:** git-pr is a pure git skill — it always creates a PR. The `require-pr-for-main` config flag belongs to helm-merge, which can block direct merges and tell users to run `/git-pr`.
**Trade-off:** git-pr cannot do direct squash merges — that remains helm-merge's job. Users without helm who want direct merge use standard git commands.
**Alternatives rejected:** Config-driven dual-mode skill (PR or direct merge based on flag) — rejected because it couples git-pr to helm config and makes the skill do two things instead of one.

## git-pr: _git/config.yaml for base branch
**Why:** git plugin config should not live in `_helm/config.yaml`. A dedicated `_git/config.yaml` keeps concerns separated. Forward-looking — file doesn't exist yet (Knatte18/millhouse#13).
**Trade-off:** Until #13 is implemented, base branch always defaults to `main` unless passed as argument.
**Alternatives rejected:** Reading `_helm/config.yaml` (couples git to helm), auto-detecting parent via `git merge-base` (unreliable, git doesn't store parent branch metadata).

## Structured plan Context with design decisions
**Why:** Plan-reviewer and code-reviewer agents had no visibility into discussion decisions. They reviewed plans/code in a vacuum, wasting rounds on already-settled questions or missing contradictions with agreed design choices.
**Trade-off:** Plans now require more structured writing in `## Context` — each significant decision needs a `### Decision:` subsection. Slightly more effort during planning, but saves review cycles.
**Alternatives rejected:** Separate `<DISCUSSION_SUMMARY>` variable injected into reviewer prompts (adds complexity, Context already in plan content). Freeform Context (too vague for reviewers to check against). Fixing only plan-reviewer (code-reviewer has the same blind spot).

## ~~Gitignore all kanban boards~~ (SUPERSEDED)
**Superseded by:** "Two-board model with tracked backlog" (below).
**Original rationale:** Only backlog was tracked, but this created unnecessary git complexity. helm-spawn copies kanban files to worktrees without git. A future GitHub-based sync would handle durable backlog persistence.
**Why superseded:** GitHub API latency made it impractical for primary sync (several seconds per call). Git-tracked backlog is simpler — syncs between PCs via normal git operations, survives `git clone`, no external dependency.

## Two-board model with tracked backlog
**Why:** Backlog (`backlog.kanban.md`) is git-tracked so it syncs between PCs. Work board (`board.kanban.md`) remains gitignored — local runtime state per worktree. Each worktree gets its own independent work board. No symlinks, no shared files, no locking.
**Trade-off:** Skills that write to backlog (helm-add, helm-sync, helm-spawn, helm-start, helm-abandon, helm-cleanup) must commit and push after each write. More git commits than the old all-gitignored model.
**Alternatives rejected:** All boards gitignored + GitHub sync (too slow). Shared board via symlinks (Windows junctions don't work with git, file symlinks need Developer Mode). Shared board in external directory (external dependency).
