---
name: workflow
description: Skill invocation table, task completion rules. ALWAYS use on startup.
---

# Workflow Skill

Rules for how work is coordinated: branch policy, task completion, and skill invocation.

---

## Skill Invocation Table

Use the appropriate skill based on the current activity:

| Situation | Skill |
|-----------|-------|
| Before editing code | `@taskmill:code-quality` |
| When running shell commands | `@taskmill:cli` |
| For project-specific style rules | `@taskmill:linting` |
| For C# comments, tests, or build | `@taskmill:csharp-*` |
| For all git operations | `@taskmill:git` |
| For file format specs (backlog, plans) | `@taskmill:formats` |
| For response style guidelines | `@taskmill:conversation` |
| For file placement and .llm/ rules | `@taskmill:llm-context` |
| For workflow and completion rules | `@taskmill:workflow` |

---

## Task Completion

- Run build + tests after each completed task (see `@taskmill:csharp-build` for details).
- When a task is fully complete, update:
  1. The plan file (all steps marked `[x]`)
  2. `doc/backlog.md` (task entry deleted)
  3. `doc/changelog.md` (dated entry describing what was done)
