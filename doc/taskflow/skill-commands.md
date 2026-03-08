# Commands Skill

Defines the commands for task management and git operations.

---

## discuss

Discuss a backlog task. Does **not** write a plan.

- Finds task from `doc/backlog.md`: by name if provided, otherwise first `[>]`, then first `[ ]`. Skips `[N]` tasks (already claimed by another thread).
- **Claims the task** by changing its state to `[N]` where N is the lowest unused digit (1-9) among current `[N]` states in the backlog. A `[>]` task keeps its priority meaning — it just gets numbered like any other.
- Writes a `started: <ISO 8601 UTC timestamp>` sub-bullet to the task in `doc/backlog.md`, recording when discussion began.
- If the task has a `plan:` sub-bullet, reads and summarizes the existing plan, then continues discussion from there.
- Reads relevant codebase sections.
- Asks clarifying questions about approach, constraints, and design.
- Discussion continues until the user calls `finalize`.
- Do not enter plan mode or write plan files. This command is discussion only.
- Do not edit any files other than `doc/backlog.md` (for claiming the task). No code edits, no file creation.

---

## finalize

Write a plan from the current discussion.

- Takes task name from argument or infers from conversation.
- Creates `.llm/plans/YYYY-MM-DD-HHMMSS-<slug>.md` (using current UTC date and time) with:
  - **YAML frontmatter:** `started:` (copied from the task's `started:` sub-bullet in `doc/backlog.md`) and `finished:` (current UTC timestamp, matches filename timestamp)
  - **Context:** summary of discussion and key decisions
  - **Files:** flat list of file paths the plan expects to modify (used for staleness detection and fast implementation start)
  - **Steps:** concrete, actionable `- [ ]` items
- Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_plan.py doc/backlog.md "<task-name>" <plan-path>` to change state to `[p]` and add/replace the `plan:` sub-bullet.
- Steps must use concrete actions (e.g. `Regenerate build output following BUILD.md`), never `/task-*` commands or `@taskmill:` skill references — the executor treats these as requiring user invocation or skill loading, stalling execution.
- Do not edit any files other than `.llm/plans/`. No code edits, no build changes. All backlog mutations go through scripts.

---

## do

Implement the next planned task. Does **not** commit.

**Frontmatter:** `model: opus`

- Finds next planned task using `--include-planned`: first `[>]` with `plan:`, then first `[p]` with `plan:`, then first `[ ]` with `plan:`.
- Reads the plan file.
- Reads all files listed in `## Files` as initial context.
- **Staleness check:** reads the `started:` timestamp from the plan's YAML frontmatter and runs `git log --since=<started-timestamp> -- <file1> <file2> ...` for the listed files. If changes are found, re-reads affected files and revises plan steps before proceeding.
- Implements each `- [ ]` step, marking as `- [x]` immediately after completion.
- If a step fails: marks `- [!]` and blocks the task via script.
- Runs build + test after all steps (detect project language and use the matching `{lang}-build` skill — see `@taskmill:workflow` Language Detection).
- If all steps complete: deletes task from `doc/backlog.md` (via `--delete`), updates `doc/changelog.md`.
- Does **not** commit — user calls `commit` when ready.

---

## do-commit

Implement the next planned task and commit. Combines `do` then `commit`.

**Frontmatter:** `model: opus`

- **Branch check first:** run `git branch --show-current`. If on `main`/`master`:
  1. Derive a branch name from the task title slug (e.g. `feature/revise-git-workflow`).
  2. Prompt: *"You're on **main**. Create branch **`<name>`** and continue there? You can also provide a different name."*
  3. Wait for user confirmation or an alternative name.
  4. Create the branch (`git checkout -b <name>`) and switch to it.
- Run `do` (implement the next planned task, mark steps, run build + test, update backlog and changelog).
- Run `commit` (stage individually, commit with title + bullet-point format, push).

---

## do-all

Implement all planned tasks, committing after each.

**Frontmatter:** `model: opus`

- **Branch check first:** same as `do-commit` — if on `main`/`master`, prompt to create a new branch, wait for confirmation, create and switch to it. One branch for the entire batch.
- Loop: run `do-commit` until no planned tasks remain (task_get.py --include-planned returns exit code 1).
- Stops when no planned tasks remain.

---

## finalize-do

Finalize the current discussion and immediately implement the resulting task. Does **not** commit.

**Frontmatter:** `model: opus`

- Takes task name from argument or infers from conversation.
- Creates `.llm/plans/YYYY-MM-DD-HHMMSS-<slug>.md` (using current UTC date and time) with YAML frontmatter, context, files, and steps. (Same as `finalize`.)
- Runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_plan.py doc/backlog.md "<task-name>" <plan-path>` to change state to `[p]` and add the `plan:` sub-bullet.
- Runs `do` on the resulting task: reads plan and listed files, staleness check, implements steps, runs build + test, updates backlog and changelog.
- Does **not** commit — user calls `commit` when ready.

---

## finalize-do-commit

Finalize the current discussion, implement the resulting task, and commit.

**Frontmatter:** `model: opus`

- **Branch check first:** run `git branch --show-current`. If on `main`/`master` and `--onmain` is not in the argument: refuse to proceed. Suggest a branch name based on the task context (e.g. `feature/task-name`), prompt the user to create it and re-run. Do not create the branch.
- Takes task name from argument or infers from conversation.
- Creates `.llm/plans/YYYY-MM-DD-HHMMSS-<slug>.md` with YAML frontmatter, context, files, and steps.
- Runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_plan.py doc/backlog.md "<task-name>" <plan-path>` to change state to `[p]` and add the `plan:` sub-bullet.
- Runs `do` on the resulting task: reads plan and listed files, staleness check, implements steps, runs build + test, updates backlog and changelog.
- Runs `commit`: stage individually, commit with title + bullet-point format, push. Set upstream if needed.

---

## finalize-do-all

Finalize the current discussion, then implement all planned tasks committing after each.

**Frontmatter:** `model: opus`

- **Branch check first:** same as `finalize-do-commit` — if on `main`/`master` and `--onmain` is not in the argument, refuse, suggest a branch name, and stop. One branch for the entire batch.
- Finalize current discussion: create plan file, run `task_plan.py` to update backlog.
- Loop: run `do-commit` (find next planned task, implement, commit) until `task_get.py --include-planned` exits with code 1 (no planned tasks remain).

---

## add-discuss

Add a new task to the backlog and immediately start discussing it.

- Takes `Title: description` as argument. Colon splitting follows the same rules as `add`: part before colon becomes the bold title, part after becomes the description.
- Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_add.py doc/backlog.md "<full argument>"` to append the task to the backlog.
- Extract the title: part before the first colon, or the full argument if no colon is present.
- Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_claim.py doc/backlog.md "<title>"` to claim the newly added task (assigns thread number, records started timestamp).
- Continue as `discuss`: read relevant codebase sections, ask clarifying questions about approach, constraints, and design. Do not write a plan file — discussion continues until the user calls `finalize`.

---

## list

Show task status and let the user pick one to discuss.

- Reads `doc/backlog.md`.
- Prints status summary: `Status: 1 prioritized | 1 in discussion | 2 planned | 3 unplanned | 1 blocked`.
- Groups open tasks by state: prioritized `[>]`, in discussion `[N]`, planned `[p]`, unplanned `[ ]`, blocked `[!]`.
- Shows plan file path and blocked reason if applicable.
- User picks a task number to start discussion (proceeds as `discuss`).

---

## add

Add an item to a file with `- [ ] **Title**` format.

- Takes file path and `Title: description` as parameters.
- If the input contains a colon, the part before becomes the bold title and the part after becomes an indented description.
- If no colon, the entire input becomes the bold title with no description.
- Works on `doc/backlog.md` and `.llm/plans/YYYY-MM-DD-HHMMSS-<slug>.md`.
- Appends the formatted entry followed by a blank line.

---

## commit

Commit and push. No rebase.

**Frontmatter:** `argument-hint: "[--onmain] [message]"`

- See `@taskmill:git` for full commit rules.
- **If on `main`/`master` and `--onmain` is not in the argument:** refuse to commit. Suggest a branch name based on the staged changes or recent context (e.g. `feature/revise-git-workflow`), prompt the user to confirm or provide an alternative name, then stop. Do not create the branch — `commit` only commits.
- **If on `main`/`master` and `--onmain` is in the argument:** proceed normally.
- Stages files individually, commits with title + bullet-point format, pushes.
- Sets upstream if needed: `git push --set-upstream origin <branch>`.

---

## log

Generate a changelog entry from recent git commits. Prints to stdout only — does not write to `doc/changelog.md`.

**Frontmatter:** `argument-hint: "[since] [language] [length/emphasis]"`

- Accepts optional arguments in any order or combination:
  - **cutoff time**: ISO 8601 timestamp or natural-language date (e.g. `yesterday`, `2026-03-01`). If omitted, reads `doc/changelog.md` and finds the date of the newest `## YYYY-MM-DD` heading, then uses that date as the cutoff.
  - **language**: e.g. `norwegian`, `french`. Default: English.
  - **length/emphasis guidance**: e.g. `brief`, `detailed`, `focus on architecture decisions`.
- Runs `git log --oneline --since=<cutoff>` to gather commits since the cutoff.
- Reads `doc/changelog.md` to match the existing tone and format.
- Generates a single entry as dense, technical narrative prose — work-journal style covering what was done, key decisions, discoveries, and open items.
- Prints the entry to stdout (with the `## YYYY-MM-DD` heading using today's date). Does NOT modify any files.
- Honors the language argument if provided; otherwise defaults to English.

---

## retry

Retry the first blocked task.

- Finds first `[!]` task with `plan:` sub-bullet in `doc/backlog.md`.
- Reads plan file, finds first `- [!]` step (or first `- [ ]` if no `[!]`).
- Implements remaining steps, marking as `- [x]`.
- If a step fails again: marks `- [!]` and stays blocked.
- If all steps complete: deletes task from `doc/backlog.md` (via `--delete`), updates changelog.
- Does **not** commit.

---

## mill-build

Build skills from `doc/` specs into `build/taskmill/` plugin structure.

Read and follow `BUILD.md`.

---

## mill-deploy

Reinstall the taskmill plugin from the local marketplace.

- Run `claude plugin uninstall taskmill@taskmill` (ignore errors if not yet installed).
- Run `claude plugin install taskmill@taskmill`.
- If `claude` is not found, try `npx @anthropic-ai/claude-code` instead.
- If both fail, print the commands for the user to run manually in a terminal.
- Remind the user to restart Claude Code after installation.
- For first-time setup, also run: `claude plugin marketplace add c:/Code/taskmill`

---

## Workflow Summary

```
backlog.md          discuss                  .llm/plans/
┌──────────┐       ┌────────────────┐       ┌───────────┐
│ - [ ] ... │──────▶│  Discussion    │──────▶│ - [ ] ... │
│ - [>] ... │       │  (no plan yet) │       │ - [ ] ... │
└──────────┘       └───────┬────────┘       └─────┬─────┘
                           │                      │
                       finalize               do
                           │                      │
                   adds plan: link         marks [x] per step
                   in backlog.md           runs build+test
                                                  │
                                           commit (manual)
                                           or auto in do-all
```
