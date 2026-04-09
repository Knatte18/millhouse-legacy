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
| mill-add | Create a new task in tasks.md |
| mill-start | Interactive discussion before execution |
| mill-go | Autonomous plan, implement, review, merge |
| mill-spawn | Create worktree and claim task |
| mill-inbox | Import GitHub issues to tasks.md |
| mill-merge | Merge completed worktree to parent |
| mill-merge-in | Merge parent branch into current branch |
| mill-abandon | Discard worktree, unmark task |
| mill-status | Dashboard of all worktrees |

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
