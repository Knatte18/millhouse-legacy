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
| Before editing code | `@code:code-quality` |
| When running shell commands | `@code:cli` |
| For project-specific style rules | `@code:linting` |
| When writing or reviewing tests | `@code:testing` (+ language-specific `{lang}-testing`) |
| For language-specific build, test, or comments | Detect language, then use `@{lang}:{lang}-*` (see below) |
| For all git operations | `@git:git-workflow` |
| For file format specs (backlog, plans) | `@taskmill:mill-formats` |
| For response style guidelines | `@orchestration:conversation` |
| For file placement and .llm/ rules | `@orchestration:llm-context` |
| For workflow and completion rules | `@orchestration:workflow` |

---

## Language Detection

Detect the project language from marker files in the working directory and use the matching skills:

| Marker files | Language | Skills |
|-------------|----------|--------|
| `pyproject.toml`, `setup.py`, `setup.cfg` | Python | `@python:python-build`, `python-comments`, `python-testing` |
| `.csproj`, `.sln` | C# | `@csharp:csharp-build`, `csharp-comments`, `csharp-testing` |

If multiple languages are present, use the skills matching the files being edited.

---

## Protected File Mutations

Never use Edit or Write on `_taskmill/backlog.md` or `.llm/plans/*.md`. All mutations must go through scripts. Reading with Read is allowed.

### Backlog (`_taskmill/backlog.md`)

| Action | Script |
|--------|--------|
| Add task | `task_add.py` |
| Claim for discussion | `task_claim.py` |
| Set planned + link plan | `task_plan.py` |
| Complete / delete | `task_complete.py` |
| Block with reason | `task_block.py` |
| Add/update sub-bullet | `task_subbullet.py` |

### Plan files (`.llm/plans/*.md`)

Write is allowed for initial creation only (the `finalize` command creates the file). After creation, all mutations go through scripts:

| Action | Script |
|--------|--------|
| Mark step done | `task_complete.py` |
| Mark step blocked | `task_block.py` |
| Add/update sub-bullet | `task_subbullet.py` |
| Set finished timestamp | `plan_finish.py` |

---

## Task Completion

- Run build + tests after each completed task (see Language Detection above to select the correct `{lang}-build` skill).
- When a task is fully complete, update:
  1. The plan file (all steps marked `[x]` via `task_complete.py`, then `plan_finish.py` to set `finished:` timestamp)
  2. `_taskmill/backlog.md` (task entry deleted via `task_complete.py --delete`)
  3. `_taskmill/changelog.md` (dated entry describing what was done)
