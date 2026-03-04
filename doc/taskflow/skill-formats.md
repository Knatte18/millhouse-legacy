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
  - plan: .llm/plans/2026-03-04-1430-refactor-validation.md

- [>] **Improve query performance**
  Profile and optimize slow database queries in the reporting module.

- [!] **Fix memory leak in cache manager**
  Cache entries are not evicted under memory pressure.
  - plan: .llm/plans/2026-03-03-0915-fix-cache-leak.md
  - blocked: Missing access to test data
```

**Task states:**

| State | Meaning | Set by |
|-------|---------|--------|
| `[ ]` | Unplanned / waiting | User or `hanf-add-task` |
| `[>]` | Prioritized / focused | User (manually) |
| `[p]` | Planned (has plan file) | `hanf-finalize-plan` |
| `[!]` | Blocked (with reason) | `hanf-task-block` script |

Completed tasks are deleted from the backlog (via `hanf_task_complete.py --delete`) since `doc/changelog.md` already records them. The `[x]` state is only used in plan files for step tracking.

**Sub-bullets:**
- `plan: <path>` — links to the implementation plan file
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

## .llm/plans/YYYY-MM-DD-HHMM-\<slug>.md (untracked)

Detailed implementation plan with checkboxed steps.

```markdown
# Refactor data validation layer

## Context
Summary of the discussion that led to this plan.
Key decisions and constraints identified.

## Steps
- [ ] Extract IValidator interface from existing validation logic
- [ ] Implement FluentValidation-based validators
- [ ] Update all call sites to use new interface
- [ ] Write tests for new validators
```

Steps are marked `[x]` progressively as CC completes them, and `[!]` if a step fails.
