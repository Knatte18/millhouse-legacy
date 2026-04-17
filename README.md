# Millhouse

Multi-plugin marketplace for Claude Code. The core plugin **mill** provides task orchestration, code quality rules, git workflow, and documentation — everything you need for AI-assisted development.

## Plugins

| Plugin | Description |
|--------|-------------|
| **mill** | Task orchestration, code quality, git workflow, documentation (core) |
| weblens | Fetch blocked/restricted web pages (requires Node.js) |
| python | Python build, comments, and testing conventions |
| csharp | C# build, comments, and testing conventions |
| taskmill-legacy | Legacy task management (archived — replaced by mill) |

## Install

See [INSTALL.md](INSTALL.md) for setup instructions.

## Skills (mill plugin)

### Task Orchestration
| Skill | Purpose |
|-------|---------|
| mill-setup | Initialize Mill for a repository |
| mill-add | Create a new task on the tasks branch |
| mill-start | Interactive discussion before execution |
| mill-go | Autonomous plan, implement, review, merge |
| mill-spawn | Create worktree and claim task |
| mill-merge | Merge completed worktree to parent |
| mill-merge-in | Merge parent branch into current branch |
| mill-abandon | Discard worktree, unmark task |
| mill-status | Dashboard of all worktrees |

## Tasks workflow

`tasks.md` lives on a dedicated orphan branch `tasks` in this repo. The branch never merges into `main` — it exists solely as a git-synced storage location for the task list. This keeps `main`'s history free of `task:`-prefixed commits from claim/done/cleanup churn.

Locally, the `tasks` branch is checked out as a persistent git worktree at `tasks.worktree-path` in `_millhouse/config.yaml` (typically `<parent-of-repo>/<reponame>.worktrees/tasks`). Open a dedicated VS Code window on that folder to view and edit tasks. On GitHub the file is viewable at `blob/tasks/tasks.md`.

All mill skills read and write tasks.md via `millpy.tasks.tasks_md.resolve_path` + `write_commit_push` — never via `git` commands in the current worktree.

Lifecycle markers: `[s]` (ready to claim) → `[active]` (claimed) → `[completed]` (mill-go finished) → `[done]` (mill-merge landed). `mill-abandon` overwrites any marker with `[abandoned]`.

### Code Quality
| Skill | Purpose |
|-------|---------|
| code-quality | Strict inputs, naming, no defensive code |
| cli | Shell command guidelines |
| linting | Project-specific style rules |
| testing | Language-agnostic testing principles |

### Git
| Skill | Purpose |
|-------|---------|
| git-workflow | Branch policy, commit format |
| git-commit | Commit and push |
| git-pr | Create GitHub Pull Request |
| git-issue | Create GitHub issue |
| git-log | Generate work journal from commits |
| git-clone | Clone as bare-repo hub with worktrees |

### Behavior
| Skill | Purpose |
|-------|---------|
| conversation | Response style: direct, no fluff |
| workflow | Skill invocation table, language detection |
| millhouse-issue | Report bugs to millhouse repo |

### Documentation
| Skill | Purpose |
|-------|---------|
| codeguide-setup | Initialize documentation structure |
| codeguide-generate | Generate docs for new source files |
| codeguide-maintain | Fix existing docs |
| codeguide-update | Update docs for changed files |
| review-navigation | Analyze navigation issues |

## Acknowledgments

Based on [claude-code-plugins](https://github.com/motlin/claude-code-plugins) by Craig Motlin.
