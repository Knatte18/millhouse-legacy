---
name: mill-formats
description: Backlog, changelog, and plan file format specs. Use when reading or writing task files.
---

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
| `[ ]` | Unplanned / waiting (with `plan:` sub-bullet: parked for later) | User, `add`, or `finalize --park` |
| `[>]` | Prioritized / focused | User (manually) |
| `[N]` | In discussion by thread N (any digit 1-9) | `discuss` |
| `[p]` | Planned (has plan file) | `finalize` |
| `[!]` | Blocked (with reason) | `task_block.py` script |

Completed tasks are deleted from the backlog (via `task_complete.py --delete`) since `doc/changelog.md` already records them. The `[x]` state is only used in plan files for step tracking.

**Sub-bullets:**
- `plan: <path>` — links to the implementation plan file
- `started: <ISO 8601 UTC timestamp>` — records when discussion began (written by `discuss`)
- `blocked: <reason>` — explains why a task is blocked

**Mutation rule:** Never use Edit or Write on `doc/backlog.md`. All mutations must go through scripts in `scripts/` (e.g. `task_plan.py`, `task_complete.py`, `task_block.py`). Reading with Read is allowed.

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
Extract validators into a clean interface. Currently validation logic is
inline in ValidationService.Process(). Use FluentValidation as the backing
library. Keep the existing ValidationService as a thin orchestrator.

## Files
- src/Services/ValidationService.cs
- src/Interfaces/IValidator.cs
- src/Validators/OrderValidator.cs
- src/Validators/CustomerValidator.cs
- tests/Validators/OrderValidatorTests.cs
- tests/Validators/CustomerValidatorTests.cs

## Steps
- [ ] Create `src/Interfaces/IValidator.cs`: define `IValidator<T>` interface with `Validate(T entity)` returning `ValidationResult`.
- [ ] Create `src/Validators/OrderValidator.cs`: implement `IValidator<Order>` using FluentValidation. Validate `OrderDate`, `TotalAmount > 0`, and `Items` not empty.
- [ ] Create `src/Validators/CustomerValidator.cs`: implement `IValidator<Customer>` using FluentValidation. Validate `Email` format and `Name` not blank.
- [ ] Update `src/Services/ValidationService.cs`: replace inline validation in `Process()` with calls to injected `IValidator<T>` instances. Register validators in DI.
- [ ] Create `tests/Validators/OrderValidatorTests.cs`: test `Validate()` with valid order, missing items, zero amount, and null date.
- [ ] Create `tests/Validators/CustomerValidatorTests.cs`: test `Validate()` with valid customer, blank name, and malformed email.
```

**YAML frontmatter:**
- `started:` — ISO 8601 UTC timestamp of when discussion began (copied from backlog `started:` sub-bullet by `finalize`)
- `finished:` — ISO 8601 UTC timestamp of when the plan was finalized (matches filename timestamp)

The `## Files` section lists files the plan expects to modify. Used for staleness detection (checking if those files changed since discussion started) and for fast implementation start (reading them upfront instead of scanning the codebase).

Steps are marked `[x]` progressively via `task_complete.py`, and `[!]` via `task_block.py` if a step fails.

**Mutation rule:** Never use Edit or Write on existing `.llm/plans/*.md` files. Write is allowed for initial creation only (the `finalize` command creates the file). After creation, all mutations go through scripts: `task_complete.py` for marking steps, `task_block.py` for blocking, `task_subbullet.py` for sub-bullets, `plan_finish.py` for setting the `finished:` timestamp. Reading with Read is allowed.

**Plan step rules:**
- **One step per file** (or a small cluster of tightly coupled files). Never bundle unrelated file operations into a single step.
- **Explicit names.** Each step must include the target file path and the specific functions, classes, or fields being added or changed.
- **No slash commands or skill references.** Steps must describe concrete actions, not reference `/taskmill.*` slash commands or `@taskmill:` skill names. The LLM executor may interpret these as requiring user invocation or skill loading, stalling execution.
- **Test steps required for source code tasks.** When `## Files` contains source code files, the plan must include steps for writing new tests or updating existing tests that cover the changes. Omit test steps only when the task is purely doc or config changes.
- Bad: `Run /taskmill.do` or `Follow @taskmill:mill-csharp-build`
- Bad: `Extract interface and implement validators` (compound, no file paths)
- Good: `Create src/Interfaces/IValidator.cs: define IValidator<T> interface with Validate(T entity) returning ValidationResult.`
