---
name: helm-abandon
description: Discard a worktree and move the task back to Backlog.
---

# helm-abandon

Discard a worktree. Moves the task back to Backlog in `.kanbn/index.md`.

1. Check for uncommitted changes. If found, warn: "This worktree has uncommitted work. Abandon anyway?"
2. Check for committed-but-unmerged work on the branch. If found, warn with commit count.
3. User confirms.
4. `git worktree remove <path>`
5. `git branch -D <branch-name>`
6. Move task to **Backlog** in `.kanbn/index.md`. Clear `phase` in task frontmatter.
7. If checkpoint branch exists: `git branch -D helm-checkpoint-<name>`

Never auto-abandon. Always require user confirmation after warnings.

<!-- TODO: Full implementation in Phase 5.3 -->
