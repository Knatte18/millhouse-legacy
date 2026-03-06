# Claude Code Skills

Customizable skill specifications for Claude Code. Fork the repo, tweak the specs to fit your workflow, and have Claude Code build working skills from them into `~/.claude/`.

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

## Known Issue: Plan Mode Conflict

Claude Code's built-in **plan mode** has its own 5-phase workflow with an `ExitPlanMode` approval gate. This conflicts with the `task-*` commands, which define their own planning lifecycle (`task-discuss` → `task-plan` → `task-do`).

**Do not enter plan mode before running `task-*` or `mill-*` commands.** If plan mode is active, the system injects override instructions that fight the task workflow — the LLM will try to call `ExitPlanMode` instead of following `task-plan`, and read-only restrictions block edits that the commands need to make.

If you accidentally enter plan mode, exit it first, then invoke the command.

---

## Recommended Settings

For the task skills to work correctly, Claude Code needs permission to run tools without constant prompting. Add the following to your `~/.claude/settings.json`, or to a local repo's `.claude/settings.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash",
      "Edit",
      "MultiEdit",
      "Read",
      "Write",
      "Bash(git push:*)"
    ],
    "deny": [
      "Bash(rm -rf:*)",
      "Bash(git reset --hard:*)",
      "Bash(git push --force:*)",
      "Bash(git push -f:*)"
    ]
  }
}
```

The `allow` list grants the tool permissions the skills rely on. The `deny` list is a safety net against destructive commands.

### Hook: Read CLAUDE.md on Every Prompt

Claude Code loads `~/.claude/CLAUDE.md` into context but does not always follow the instructions inside it (e.g., reading referenced skill files). A `UserPromptSubmit` hook fixes this by reminding the model at the start of every prompt:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Read ~/.claude/CLAUDE.md and follow its instructions before responding.'"
          }
        ]
      }
    ]
  }
}
```

Merge this into your existing `~/.claude/settings.json`.

---

## Acknowledgments

Based on [claude-code-plugins](https://github.com/motlin/claude-code-plugins) by Craig Motlin.
