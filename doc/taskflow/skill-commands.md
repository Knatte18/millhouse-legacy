# Commands Skill

Defines the task-* and mill-* commands for task management and git operations.

---

## task-discuss

Discuss a backlog task. Does **not** write a plan.

- Finds task from `doc/backlog.md`: by name if provided, otherwise first `[>]`, then first `[ ]`. Skips `[N]` tasks (already claimed by another thread).
- **Claims the task** by changing its state to `[N]` where N is the lowest unused digit (1-9) among current `[N]` states in the backlog. A `[>]` task keeps its priority meaning — it just gets numbered like any other.
- Writes a `started: <ISO 8601 UTC timestamp>` sub-bullet to the task in `doc/backlog.md`, recording when discussion began.
- If the task has a `plan:` sub-bullet, reads and summarizes the existing plan, then continues discussion from there.
- Reads relevant codebase sections.
- Asks clarifying questions about approach, constraints, and design.
- Discussion continues until the user calls `task-plan`.
- Do not enter plan mode or write plan files. This command is discussion only.

---

## task-plan

Write a plan from the current discussion.

- Takes task name from argument or infers from conversation.
- Creates `.llm/plans/YYYY-MM-DD-HHMMSS-<slug>.md` (using current UTC date and time) with:
  - **YAML frontmatter:** `started:` (copied from the task's `started:` sub-bullet in `doc/backlog.md`) and `finished:` (current UTC timestamp, matches filename timestamp)
  - **Context:** summary of discussion and key decisions
  - **Files:** flat list of file paths the plan expects to modify (used for staleness detection and fast implementation start)
  - **Steps:** concrete, actionable `- [ ]` items
- Adds `plan:` sub-bullet in `doc/backlog.md` linking to the plan file.
- Changes task state to `[p]` (planned) in `doc/backlog.md`.
- Steps must use concrete actions (e.g. `Regenerate build output following BUILD.md`), never `/task-*` commands or `~/.claude/skills/` references — the executor treats these as user-invocable, stalling execution.

---

## task-do

Implement the next planned task. Does **not** commit.

**Frontmatter:** `model: sonnet`

- Finds next planned task using `--include-planned`: first `[>]` with `plan:`, then first `[p]` with `plan:`, then first `[ ]` with `plan:`.
- Reads the plan file.
- Reads all files listed in `## Files` as initial context.
- **Staleness check:** reads the `started:` timestamp from the plan's YAML frontmatter and runs `git log --since=<started-timestamp> -- <file1> <file2> ...` for the listed files. If changes are found, re-reads affected files and revises plan steps before proceeding.
- Implements each `- [ ]` step, marking as `- [x]` immediately after completion.
- If a step fails: marks `- [!]` and blocks the task via script.
- Runs build + test after all steps (see `skill-build`).
- If all steps complete: deletes task from `doc/backlog.md` (via `--delete`), updates `doc/changelog.md`.
- Does **not** commit — user calls `mill-commit` when ready.

---

## task-do-all

Implement all planned tasks. Commits after **each** completed task.

**Frontmatter:** `model: sonnet`

- Loops through planned tasks using `--include-planned` (those with `plan:` sub-bullet, priority: `[>]` → `[p]` → `[ ]`).
- For each task:
  1. Read the plan file and all files listed in `## Files`. Run the same staleness check as `task-do` (using `started:` from plan frontmatter); if changes found, re-read affected files and revise plan steps.
  2. Implement each `- [ ]` step, marking as `- [x]`.
  3. If a step fails: mark `- [!]`, block the task, move to the next task.
  4. Run build + test.
  5. Delete task from `doc/backlog.md` (via `--delete`), update `doc/changelog.md`.
  6. Commit and push (using `mill-commit` workflow).
- Stops when no planned tasks remain.

---

## task-list

Show task status and let the user pick one to discuss.

- Reads `doc/backlog.md`.
- Prints status summary: `Status: 1 prioritized | 1 in discussion | 2 planned | 3 unplanned | 1 blocked`.
- Groups open tasks by state: prioritized `[>]`, in discussion `[N]`, planned `[p]`, unplanned `[ ]`, blocked `[!]`.
- Shows plan file path and blocked reason if applicable.
- User picks a task number to start discussion (proceeds as `task-discuss`).

---

## task-add

Add an item to a file with `- [ ] **Title**` format.

- Takes file path and `Title: description` as parameters.
- If the input contains a colon, the part before becomes the bold title and the part after becomes an indented description.
- If no colon, the entire input becomes the bold title with no description.
- Works on both `doc/backlog.md` and `.llm/plans/YYYY-MM-DD-HHMMSS-<slug>.md`.
- Appends the formatted entry followed by a blank line.

---

## mill-commit

Commit and push. No rebase.

- See `git/skill-git` for full commit rules.
- Stages files individually, commits with title + bullet-point format, pushes.
- Sets upstream if needed: `git push --set-upstream origin <branch>`.

---

## task-retry

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
backlog.md          task-discuss             .llm/plans/
┌──────────┐       ┌────────────────┐       ┌───────────┐
│ - [ ] ... │──────▶│  Discussion    │──────▶│ - [ ] ... │
│ - [>] ... │       │  (no plan yet) │       │ - [ ] ... │
└──────────┘       └───────┬────────┘       └─────┬─────┘
                           │                      │
                       task-plan              task-do
                           │                      │
                   adds plan: link         marks [x] per step
                   in backlog.md           runs build+test
                                                  │
                                           mill-commit (manual)
                                           or auto in task-do-all
```
