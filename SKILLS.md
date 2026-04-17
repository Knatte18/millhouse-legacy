# Skills

| Skill | Description |
|---|---|
| [cli](plugins/mill/skills/cli/SKILL.md) | Shell command guidelines. Use when running shell commands. |
| [code-quality](plugins/mill/skills/code-quality/SKILL.md) | Strict, clean code guidelines. Use before editing code. |
| [codeguide-generate](plugins/mill/skills/codeguide-generate/SKILL.md) | Generate _codeguide/ documentation for source files that have no docs yet. Works for new and existing projects. |
| [codeguide-maintain](plugins/mill/skills/codeguide-maintain/SKILL.md) | Fix existing docs: content accuracy, structural violations, pointers, links, local-rules. Heavy, scoped. |
| [codeguide-setup](plugins/mill/skills/codeguide-setup/SKILL.md) | Set up, refresh, or activate codeguide. Detects context automatically: first-time root, refresh, or subfolder. |
| [codeguide-update](plugins/mill/skills/codeguide-update/SKILL.md) | Update docs for recently changed source files. Default: current git diff. Lightweight, safe for commit-time use. |
| [conversation](plugins/mill/skills/conversation/SKILL.md) | Response style and behavior rules. ALWAYS use on startup. |
| [csharp-build](plugins/csharp/skills/csharp-build/SKILL.md) | Build and test commands for C#/.NET. Use after completing a task. |
| [csharp-comments](plugins/csharp/skills/csharp-comments/SKILL.md) | XML doc and inline comment rules for C#/.NET. Use when writing C# comments. |
| [csharp-testing](plugins/csharp/skills/csharp-testing/SKILL.md) | Testing conventions for C#/.NET projects. Use when writing tests. |
| [git-clone](plugins/mill/skills/git-clone/SKILL.md) | Clone a repo as a bare-repo hub with worktrees |
| [git-commit](plugins/mill/skills/git-commit/SKILL.md) | Commit and push (no rebase) |
| [git-issue](plugins/mill/skills/git-issue/SKILL.md) | Create a GitHub issue on the current repo |
| [git-log](plugins/mill/skills/git-log/SKILL.md) | Generate a work-journal entry from recent commits |
| [git-pr](plugins/mill/skills/git-pr/SKILL.md) | Create a GitHub Pull Request from the current branch |
| [git-workflow](plugins/mill/skills/git-workflow/SKILL.md) | Git workflow and commit rules. Use for all git operations. |
| [legacy-mill-add](plugins/taskmill-legacy/skills/legacy-mill-add/SKILL.md) | Add a checkbox item to a file |
| [legacy-mill-add-discuss](plugins/taskmill-legacy/skills/legacy-mill-add-discuss/SKILL.md) | Add a task and start discussing it |
| [legacy-mill-commit](plugins/taskmill-legacy/skills/legacy-mill-commit/SKILL.md) | Commit and push (no rebase) |
| [legacy-mill-discuss](plugins/taskmill-legacy/skills/legacy-mill-discuss/SKILL.md) | Discuss a backlog task without writing a plan |
| [legacy-mill-do](plugins/taskmill-legacy/skills/legacy-mill-do/SKILL.md) | Implement the next planned task (does not commit) |
| [legacy-mill-do-all](plugins/taskmill-legacy/skills/legacy-mill-do-all/SKILL.md) | Implement all planned tasks, committing after each |
| [legacy-mill-do-commit](plugins/taskmill-legacy/skills/legacy-mill-do-commit/SKILL.md) | Implement the next planned task and commit |
| [legacy-mill-finalize](plugins/taskmill-legacy/skills/legacy-mill-finalize/SKILL.md) | Write a plan from the current discussion |
| [legacy-mill-finalize-do](plugins/taskmill-legacy/skills/legacy-mill-finalize-do/SKILL.md) | Finalize the current discussion and implement that task (no commit) |
| [legacy-mill-finalize-do-all](plugins/taskmill-legacy/skills/legacy-mill-finalize-do-all/SKILL.md) | Finalize, then implement all planned tasks |
| [legacy-mill-finalize-do-commit](plugins/taskmill-legacy/skills/legacy-mill-finalize-do-commit/SKILL.md) | Finalize, implement, and commit |
| [legacy-mill-formats](plugins/taskmill-legacy/skills/legacy-mill-formats/SKILL.md) | Backlog, changelog, and plan file format specs. Use when reading or writing task files. |
| [legacy-mill-list](plugins/taskmill-legacy/skills/legacy-mill-list/SKILL.md) | Show task status and pick one to discuss |
| [legacy-mill-log](plugins/taskmill-legacy/skills/legacy-mill-log/SKILL.md) | Generate a work-journal entry from recent commits |
| [legacy-mill-retry](plugins/taskmill-legacy/skills/legacy-mill-retry/SKILL.md) | Retry the first blocked task |
| [legacy-mill-review](plugins/taskmill-legacy/skills/legacy-mill-review/SKILL.md) | Review a plan by spawning a fresh agent with no conversation context |
| [linting](plugins/mill/skills/linting/SKILL.md) | Project-specific linting and style rules. Use for style decisions. |
| [markdown](plugins/mill/skills/markdown/SKILL.md) | Markdown formatting rules for generated files. Use when writing .md files. |
| [mill-abandon](plugins/mill/skills/mill-abandon/SKILL.md) | Mark a worktree task as abandoned. Captures abandon protocol and updates task status; git cleanup is deferred to mill-cleanup. |
| [mill-add](plugins/mill/skills/mill-add/SKILL.md) | Create a new task in tasks.md. |
| [mill-cleanup](plugins/mill/skills/mill-cleanup/SKILL.md) | Clean up merged, abandoned, and stale worktrees, branches, and task entries. |
| [mill-go](plugins/mill/skills/mill-go/SKILL.md) | Full autonomous execution engine — pre-arm wait, DAG-aware implementation, code review, merge. |
| [mill-inspect](plugins/mill/skills/mill-inspect/SKILL.md) | Toggle inspect mode to view mill-go changes as uncommitted diffs in VS Code. |
| [mill-merge](plugins/mill/skills/mill-merge/SKILL.md) | Merge a completed worktree back to its parent branch. |
| [mill-merge-in](plugins/mill/skills/mill-merge-in/SKILL.md) | Merge parent branch into the current branch. Standalone sync operation. |
| [mill-plan](plugins/mill/skills/mill-plan/SKILL.md) | Autonomous plan writing phase — writes v3 flat-card plan from discussion file and reviews it. |
| [mill-receiving-review](plugins/mill/skills/mill-receiving-review/SKILL.md) | Decision tree for evaluating reviewer findings. MUST be invoked BEFORE reading any reviewer output. |
| [mill-revise-tasks](plugins/mill/skills/mill-revise-tasks/SKILL.md) | Drain GitHub issue queue into tasks.md — fetch, status-check, brevity-cleanup of existing tasks, consolidate, propose, then write on user approval. |
| [mill-self-report](plugins/mill/skills/mill-self-report/SKILL.md) | Reflect on session activity and file detected bugs as GitHub issues. Auto-invoked by mill-plan/mill-go at end-of-work; can also be invoked manually. |
| [mill-setup](plugins/mill/skills/mill-setup/SKILL.md) | Initialize Mill for a repository. Creates tasks.md, config, directory structure, and forwarding wrappers. |
| [mill-skills-index](plugins/mill/skills/mill-skills-index/SKILL.md) | Regenerate SKILLS.md (repo root) and per-plugin INDEX.md from SKILL.md frontmatter. Manual invocation only — no pre-commit hook. |
| [mill-spawn](plugins/mill/skills/mill-spawn/SKILL.md) | Add a task to tasks.md and create a worktree for it in one command. |
| [mill-start](plugins/mill/skills/mill-start/SKILL.md) | Pick a task and design the solution through interactive discussion. Produces a discussion file for mill-plan. |
| [mill-status](plugins/mill/skills/mill-status/SKILL.md) | Dashboard showing all active worktrees and their state. |
| [millhouse-issue](plugins/mill/skills/millhouse-issue/SKILL.md) | Report bugs, suggestions, or corrections to the millhouse repo from any repo. Invoke as /millhouse-issue "your message here". |
| [python-build](plugins/python/skills/python-build/SKILL.md) | Build and test commands for Python projects. Use after completing a task. |
| [python-comments](plugins/python/skills/python-comments/SKILL.md) | Docstring and inline comment rules for Python. Use when writing Python comments. |
| [python-testing](plugins/python/skills/python-testing/SKILL.md) | Testing conventions for Python projects. Use when writing tests. |
| [review-handler](plugins/mill/skills/review-handler/SKILL.md) | Synthesize N reviewer reports into a single combined report. Verify findings by re-reading cited file:line. Classify severity, dedupe, resolve verdict on dissent, write combined report. |
| [review-navigation](plugins/mill/skills/review-navigation/SKILL.md) | Read _codeguide/runtime/navigation-issues.md and propose improvements to prevent recurrence. |
| [testing](plugins/mill/skills/testing/SKILL.md) | Language-agnostic testing principles. Use when writing or reviewing tests. |
| [weblens](plugins/weblens/skills/weblens/SKILL.md) | Fetch blocked/restricted web pages and answer questions about their content |
| [workflow](plugins/mill/skills/workflow/SKILL.md) | Skill invocation table and language detection. ALWAYS use on startup. |
