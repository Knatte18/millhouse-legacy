# Claude Code Skills

Shareable skill specifications for Claude Code. Colleagues can customize these specs and have Claude Code build working skills from them into `~/.claude/`.

---

## Core (always active)

Foundational rules that apply to every interaction.

| Skill | Purpose |
|-------|---------|
| [skill-conversation](doc/core/skill-conversation.md) | Response style: direct, no fluff, no compliments |
| [skill-llm-context](doc/core/skill-llm-context.md) | Directory structure, .llm/ rules, file writing policy |
| [skill-workflow](doc/core/skill-workflow.md) | Skill invocation table, task completion rules |

## Coding (contextual)

Applied when writing, reviewing, or building code. Language-agnostic skills at the top level, language-specific in subfolders.

| Skill | Purpose |
|-------|---------|
| [skill-code-quality](doc/coding/skill-code-quality.md) | Strict inputs, no defensive try/catch, naming |
| [skill-cli](doc/coding/skill-cli.md) | Absolute paths, long flags |
| [skill-linting](doc/coding/skill-linting.md) | Project-specific rules (extensible) |

### C# / .NET

| Skill | Purpose |
|-------|---------|
| [skill-comments](doc/coding/csharp/skill-comments.md) | XML doc, inline comments, prohibited patterns |
| [skill-testing](doc/coding/csharp/skill-testing.md) | Test framework and conventions (swappable) |
| [skill-build](doc/coding/csharp/skill-build.md) | Build/test commands and failure handling |

## Git

Git workflow and commit rules.

| Skill | Purpose |
|-------|---------|
| [skill-git](doc/git/skill-git.md) | Branch policy, commit format, staging, push |

## Taskflow

Commands, scripts, and file formats for planning and executing work.

| Skill | Purpose |
|-------|---------|
| [skill-commands](doc/taskflow/skill-commands.md) | task-* and mill-* commands (discuss, plan, execute, commit) |
| [skill-formats](doc/taskflow/skill-formats.md) | backlog.md, changelog.md, plan file format |
| [skill-scripts](doc/taskflow/skill-scripts.md) | Python scripts for checkbox file operations |

---

## Build and Deploy

Specs in `doc/` are transformed into working Claude Code files in `build/`, then deployed to a target.

| Command | What it does |
|---------|-------------|
| `/mill-build` | Reads specs from `doc/`, generates skills, commands, and scripts into `build/` |
| `/mill-deploy` | Copies `build/` to `~/.claude/` (default) or a given path |

See [BUILD.md](BUILD.md) for the full build spec.

---

## Acknowledgments

Based on [claude-code-plugins](https://github.com/motlin/claude-code-plugins) by Craig Motlin.
