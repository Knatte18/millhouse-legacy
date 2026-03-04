# Commands Skill

Defines the 8 hanf-* commands for task management and git operations.

---

## hanf-discuss-task

Discuss a backlog task. Does **not** write a plan.

- Finds task from `doc/backlog.md`: by name if provided, otherwise first `[>]`, then first `[ ]`.
- If the task has a `plan:` sub-bullet, reads and summarizes the existing plan, then continues discussion from there.
- Reads relevant codebase sections.
- Asks clarifying questions about approach, constraints, and design.
- Discussion continues until the user calls `hanf-finalize-plan`.

---

## hanf-finalize-plan

Write a plan from the current discussion.

- Takes task name from argument or infers from conversation.
- Creates `.llm/plans/YYYY-MM-DD-HHMM-<slug>.md` (using current UTC date and time) with:
  - **Context:** summary of discussion and key decisions
  - **Steps:** concrete, actionable `- [ ]` items
- Adds `plan:` sub-bullet in `doc/backlog.md` linking to the plan file.
- Changes task state to `[p]` (planned) in `doc/backlog.md`.

---

## hanf-do-planned-task

Implement the next planned task. Does **not** commit.

- Finds next planned task using `--include-planned`: first `[>]` with `plan:`, then first `[p]` with `plan:`, then first `[ ]` with `plan:`.
- Reads the plan file.
- Implements each `- [ ]` step, marking as `- [x]` immediately after completion.
- If a step fails: marks `- [!]` and blocks the task via script.
- Runs build + test after all steps (see `skill-build`).
- If all steps complete: deletes task from `doc/backlog.md` (via `--delete`), updates `doc/changelog.md`.
- Does **not** commit — user calls `hanf-commit` when ready.

---

## hanf-do-all-planned

Implement all planned tasks. Commits after **each** completed task.

- Loops through planned tasks using `--include-planned` (those with `plan:` sub-bullet, priority: `[>]` → `[p]` → `[ ]`).
- For each task:
  1. Read the plan file.
  2. Implement each `- [ ]` step, marking as `- [x]`.
  3. If a step fails: mark `- [!]`, block the task, move to the next task.
  4. Run build + test.
  5. Delete task from `doc/backlog.md` (via `--delete`), update `doc/changelog.md`.
  6. Commit and push (using `hanf-commit` workflow).
- Stops when no planned tasks remain.

---

## hanf-list-tasks

Show task status and let the user pick one to discuss.

- Reads `doc/backlog.md`.
- Prints status summary: `Status: 1 prioritized | 2 planned | 3 unplanned | 1 blocked`.
- Groups open tasks by state: prioritized `[>]`, planned `[p]`, unplanned `[ ]`, blocked `[!]`.
- Shows plan file path and blocked reason if applicable.
- User picks a task number to start discussion (proceeds as `hanf-discuss-task`).

---

## hanf-add-task

Add an item to a file with `- [ ] **Title**` format.

- Takes file path and `Title: description` as parameters.
- If the input contains a colon, the part before becomes the bold title and the part after becomes an indented description.
- If no colon, the entire input becomes the bold title with no description.
- Works on both `doc/backlog.md` and `.llm/plans/YYYY-MM-DD-HHMM-<slug>.md`.
- Appends the formatted entry followed by a blank line.

---

## hanf-commit

Commit and push. No rebase.

- See `git/skill-git` for full commit rules.
- Stages files individually, commits with title + bullet-point format, pushes.
- Sets upstream if needed: `git push --set-upstream origin <branch>`.

---

## hanf-retry-blocked

Retry the first blocked task.

- Finds first `[!]` task with `plan:` sub-bullet in `doc/backlog.md`.
- Reads plan file, finds first `- [!]` step (or first `- [ ]` if no `[!]`).
- Implements remaining steps, marking as `- [x]`.
- If a step fails again: marks `- [!]` and stays blocked.
- If all steps complete: deletes task from `doc/backlog.md` (via `--delete`), updates changelog.
- Does **not** commit.

---

## Workflow Summary

```
backlog.md          hanf-discuss-task        .llm/plans/
┌──────────┐       ┌────────────────┐       ┌───────────┐
│ - [ ] ... │──────▶│  Discussion    │──────▶│ - [ ] ... │
│ - [>] ... │       │  (no plan yet) │       │ - [ ] ... │
└──────────┘       └───────┬────────┘       └─────┬─────┘
                           │                      │
                   hanf-finalize-plan      hanf-do-planned-task
                           │                      │
                   adds plan: link         marks [x] per step
                   in backlog.md           runs build+test
                                                  │
                                           hanf-commit (manual)
                                           or auto in hanf-do-all-planned
```
