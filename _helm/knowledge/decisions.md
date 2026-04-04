## Separate kanban boards
**Why:** The VS Code kanban.md extension shows each `.kanban.md` file as a separate visual board. Having one board per column gives a cleaner UI with focused views (backlog only, in-progress only, etc.)
**Trade-off:** "Move task" is now a cross-file operation (cut from one file, paste into another) instead of an in-file edit. Slightly more complex for skills, but the mapping from column to file is 1:1 and deterministic.
**Alternatives rejected:** Single file with all columns (original design — visually cluttered), directory of per-task files (too granular, extension doesn't support it well)

## git-pr: always PR, no config flag
**Why:** git-pr is a pure git skill — it always creates a PR. The `require-pr-for-main` config flag belongs to helm-merge, which can block direct merges and tell users to run `/git-pr`.
**Trade-off:** git-pr cannot do direct squash merges — that remains helm-merge's job. Users without helm who want direct merge use standard git commands.
**Alternatives rejected:** Config-driven dual-mode skill (PR or direct merge based on flag) — rejected because it couples git-pr to helm config and makes the skill do two things instead of one.

## git-pr: _git/config.yaml for base branch
**Why:** git plugin config should not live in `_helm/config.yaml`. A dedicated `_git/config.yaml` keeps concerns separated. Implemented — `_git/config.yaml` now exists with `base-branch` and `parent-branch` fields. Created by `spawn-worktree.ps1` in target worktrees and by `helm-setup` in root worktrees.
**Trade-off:** `_git/` is gitignored (per-worktree state). Root worktree needs manual or helm-setup creation.
**Alternatives rejected:** Reading `_helm/config.yaml` (couples git to helm), auto-detecting parent via `git merge-base` (unreliable, git doesn't store parent branch metadata).

## Worktree config: drop templates, use built-in naming

**Why:** `spawn-worktree.ps1` already had sensible naming logic (hub detection, `-wt-` pattern). Configurable templates in `_helm/config.yaml` duplicated this without adding value — defaults were never changed. Removing them simplifies the codebase and decouples git from helm.
**Trade-off:** Directory placement changes for hub layouts (siblings under hub root instead of `{repo-name}-worktrees/` subfolder). Pre-existing `{repo-name}-worktrees/` directories are no longer cleaned up by helm-status.
**Alternatives rejected:** Moving templates to `_git/config.yaml` (unnecessary complexity). File symlinks from plugin to repo root (Windows requires Developer Mode). Adding plugin scripts to PATH (varies per machine).

## Structured plan Context with design decisions
**Why:** Plan-reviewer and code-reviewer agents had no visibility into discussion decisions. They reviewed plans/code in a vacuum, wasting rounds on already-settled questions or missing contradictions with agreed design choices.
**Trade-off:** Plans now require more structured writing in `## Context` — each significant decision needs a `### Decision:` subsection. Slightly more effort during planning, but saves review cycles.
**Alternatives rejected:** Separate `<DISCUSSION_SUMMARY>` variable injected into reviewer prompts (adds complexity, Context already in plan content). Freeform Context (too vague for reviewers to check against). Fixing only plan-reviewer (code-reviewer has the same blind spot).

## Gitignore all kanban boards
**Why:** Only backlog was tracked, but this created unnecessary git complexity (staging rules, conflict-resolution logic, "don't commit alone" constraints). helm-spawn already copies kanban files to worktrees without git. A future GitHub-based sync will handle durable backlog persistence.
**Trade-off:** Backlog doesn't survive `git clone` — must run helm-setup or sync from GitHub. Local task state can be lost if worktree is deleted.
**Alternatives rejected:** Keep backlog tracked (too much git ceremony for one file), track all 4 files (original design — conflict resolution was complex and error-prone)
