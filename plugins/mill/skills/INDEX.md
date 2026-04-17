# Mill Skills

| Skill | Description |
|---|---|
| [cli](cli/SKILL.md) | Shell command guidelines. Use when running shell commands. |
| [code-quality](code-quality/SKILL.md) | Strict, clean code guidelines. Use before editing code. |
| [codeguide-generate](codeguide-generate/SKILL.md) | Generate _codeguide/ documentation for source files that have no docs yet. Works for new and existing projects. |
| [codeguide-maintain](codeguide-maintain/SKILL.md) | Fix existing docs: content accuracy, structural violations, pointers, links, local-rules. Heavy, scoped. |
| [codeguide-setup](codeguide-setup/SKILL.md) | Set up, refresh, or activate codeguide. Detects context automatically: first-time root, refresh, or subfolder. |
| [codeguide-update](codeguide-update/SKILL.md) | Update docs for recently changed source files. Default: current git diff. Lightweight, safe for commit-time use. |
| [conversation](conversation/SKILL.md) | Response style and behavior rules. ALWAYS use on startup. |
| [git-clone](git-clone/SKILL.md) | Clone a repo as a bare-repo hub with worktrees |
| [git-commit](git-commit/SKILL.md) | Commit and push (no rebase) |
| [git-issue](git-issue/SKILL.md) | Create a GitHub issue on the current repo |
| [git-log](git-log/SKILL.md) | Generate a work-journal entry from recent commits |
| [git-pr](git-pr/SKILL.md) | Create a GitHub Pull Request from the current branch |
| [git-workflow](git-workflow/SKILL.md) | Git workflow and commit rules. Use for all git operations. |
| [linting](linting/SKILL.md) | Project-specific linting and style rules. Use for style decisions. |
| [markdown](markdown/SKILL.md) | Markdown formatting rules for generated files. Use when writing .md files. |
| [mill-abandon](mill-abandon/SKILL.md) | Mark a worktree task as abandoned. Captures abandon protocol and updates task status; git cleanup is deferred to mill-cleanup. |
| [mill-add](mill-add/SKILL.md) | Create a new task in tasks.md. |
| [mill-cleanup](mill-cleanup/SKILL.md) | Clean up merged, abandoned, and stale worktrees, branches, and task entries. |
| [mill-go](mill-go/SKILL.md) | Full autonomous execution engine — pre-arm wait, DAG-aware implementation, code review, merge. |
| [mill-inspect](mill-inspect/SKILL.md) | Toggle inspect mode to view mill-go changes as uncommitted diffs in VS Code. |
| [mill-merge](mill-merge/SKILL.md) | Merge a completed worktree back to its parent branch. |
| [mill-merge-in](mill-merge-in/SKILL.md) | Merge parent branch into the current branch. Standalone sync operation. |
| [mill-plan](mill-plan/SKILL.md) | Autonomous plan writing phase — writes v3 flat-card plan from discussion file and reviews it. |
| [mill-receiving-review](mill-receiving-review/SKILL.md) | Decision tree for evaluating reviewer findings. MUST be invoked BEFORE reading any reviewer output. |
| [mill-revise-tasks](mill-revise-tasks/SKILL.md) | Drain GitHub issue queue into tasks.md — fetch, status-check, brevity-cleanup of existing tasks, consolidate, propose, then write on user approval. |
| [mill-self-report](mill-self-report/SKILL.md) | Reflect on session activity and file detected bugs as GitHub issues. Auto-invoked by mill-plan/mill-go at end-of-work; can also be invoked manually. |
| [mill-setup](mill-setup/SKILL.md) | Initialize Mill for a repository. Creates tasks.md, config, directory structure, and forwarding wrappers. |
| [mill-skills-index](mill-skills-index/SKILL.md) | Regenerate SKILLS.md (repo root) and per-plugin INDEX.md from SKILL.md frontmatter. Manual invocation only — no pre-commit hook. |
| [mill-spawn](mill-spawn/SKILL.md) | Add a task to tasks.md and create a worktree for it in one command. |
| [mill-start](mill-start/SKILL.md) | Pick a task and design the solution through interactive discussion. Produces a discussion file for mill-plan. |
| [mill-status](mill-status/SKILL.md) | Dashboard showing all active worktrees and their state. |
| [millhouse-issue](millhouse-issue/SKILL.md) | Report bugs, suggestions, or corrections to the millhouse repo from any repo. Invoke as /millhouse-issue "your message here". |
| [review-handler](review-handler/SKILL.md) | Synthesize N reviewer reports into a single combined report. Verify findings by re-reading cited file:line. Classify severity, dedupe, resolve verdict on dissent, write combined report. |
| [review-navigation](review-navigation/SKILL.md) | Read _codeguide/runtime/navigation-issues.md and propose improvements to prevent recurrence. |
| [testing](testing/SKILL.md) | Language-agnostic testing principles. Use when writing or reviewing tests. |
| [workflow](workflow/SKILL.md) | Skill invocation table and language detection. ALWAYS use on startup. |
