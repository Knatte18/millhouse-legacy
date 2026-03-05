# File Formats Skill

Defines the format for backlog, changelog, and plan files.

---

## doc/backlog.md (tracked)

High-level task list. Manually maintained by the user, updated by commands.

```markdown
- [ ] **Add CSV export to reports**
  Export report data as CSV with streaming support for large datasets.

- [p] **Refactor data validation layer**
  Extract validators into a clean interface using FluentValidation.
  - plan: .llm/plans/2026-03-04-143000-refactor-validation.md

- [>] **Improve query performance**
  Profile and optimize slow database queries in the reporting module.

- [1] **Add structured logging**
  Configure Serilog with JSON output for production diagnostics.
  - started: 2026-03-04T14:30:00Z

- [!] **Fix memory leak in cache manager**
  Cache entries are not evicted under memory pressure.
  - plan: .llm/plans/2026-03-03-091500-fix-cache-leak.md
  - blocked: Missing access to test data
```

**Task states:**

| State | Meaning | Set by |
|-------|---------|--------|
| `[ ]` | Unplanned / waiting | User or `task-add` |
| `[>]` | Prioritized / focused | User (manually) |
| `[N]` | In discussion by thread N (any digit 1-9) | `task-discuss` |
| `[p]` | Planned (has plan file) | `task-plan` |
| `[!]` | Blocked (with reason) | `task_block.py` script |

Completed tasks are deleted from the backlog (via `task_complete.py --delete`) since `doc/changelog.md` already records them. The `[x]` state is only used in plan files for step tracking.

**Sub-bullets:**
- `plan: <path>` — links to the implementation plan file
- `started: <ISO 8601 UTC timestamp>` — records when discussion began (written by `task-discuss`)
- `blocked: <reason>` — explains why a task is blocked

---

## doc/changelog.md (tracked)

Dated log of completed work. Each entry gets its own heading with date and bold title. Newest entries first. Date repeats if multiple tasks complete on the same day.

```markdown
## 2026-03-04 **Added CSV export to reports**
- Used CsvHelper library for serialization
- Added streaming for large datasets

## 2026-03-04 **Added structured logging**
- Configured Serilog with JSON output
```

---

## .llm/plans/YYYY-MM-DD-HHMMSS-\<slug>.md (untracked)

Detailed implementation plan with checkboxed steps. Includes YAML frontmatter with timestamps.

```markdown
---
started: 2026-03-04T14:30:00Z
finished: 2026-03-04T15:45:00Z
---

# Refactor data validation layer

## Context
Summary of the discussion that led to this plan.
Key decisions and constraints identified.

## Files
- src/Services/ValidationService.cs
- src/Interfaces/IValidator.cs
- tests/ValidationTests.cs

## Steps
- [ ] Extract IValidator interface from existing validation logic
- [ ] Implement FluentValidation-based validators
- [ ] Update all call sites to use new interface
- [ ] Write tests for new validators
```

**YAML frontmatter:**
- `started:` — ISO 8601 UTC timestamp of when discussion began (copied from backlog `started:` sub-bullet by `task-plan`)
- `finished:` — ISO 8601 UTC timestamp of when the plan was finalized (matches filename timestamp)

The `## Files` section lists files the plan expects to modify. Used for staleness detection (checking if those files changed since discussion started) and for fast implementation start (reading them upfront instead of scanning the codebase).

Steps are marked `[x]` progressively as CC completes them, and `[!]` if a step fails.

**Plan step rules:**
- Steps must describe concrete actions, not reference `/task-*` slash commands or `~/.claude/skills/` files. The LLM executor may interpret these as requiring user invocation or skill loading, stalling execution.
- Bad: `Run /mill-build` or `Follow ~/.claude/skills/csharp-build.md`
- Good: `Regenerate build output following BUILD.md`
