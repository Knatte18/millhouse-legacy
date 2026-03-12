# Commands Reference

Human-readable reference for task management and git operation commands. This file does **not** drive the build — command source files are `doc/taskflow/commands/skill-<name>.md`, copied verbatim to `build/taskmill/skills/<name>/SKILL.md`.

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
  - **Steps:** concrete, actionable `- [ ]` items (see step-writing rules below)
- **Park flag (`--park`):** When `--park` is in the argument, pass `--state ' '` to `task_plan.py` instead of the default `[p]`. This sets the task back to `[ ]` while preserving the `plan:` sub-bullet, signaling "partially discussed, parked for later." The `do` command requires `[p]`, so parked tasks won't execute.
- **Incomplete discussion guard:** If the discussion has not produced concrete, complete steps covering all aspects of the task, prompt the user: *"This discussion seems incomplete. Finalize as planned (`[p]`) or park for later (`--park`)?"* Wait for the user's choice before proceeding.
- Run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_plan.py doc/backlog.md "<task-name>" <plan-path>` to change state to `[p]` and add/replace the `plan:` sub-bullet. With `--park`: run `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_plan.py --state ' ' doc/backlog.md "<task-name>" <plan-path>` instead.
- Do not edit any files other than `.llm/plans/`. No code edits, no build changes. All backlog mutations go through scripts.

### Step-writing rules

- **One step per file** (or a small cluster of tightly coupled files). Never bundle "create X, then wire it into Y, then update Z" into a single step.
- **Explicit names.** Each step must include the target file path and the specific functions, classes, or fields being added or changed.
- **No slash commands or skill references.** Steps must describe concrete actions, never `/taskmill.*` commands or `@taskmill:` skill names — the executor treats these as requiring user invocation, stalling execution.
- **Test steps required for source code tasks.** When `## Files` contains source code files, the plan must include steps for writing new tests or updating existing tests that cover the changes. Omit test steps only when the task is purely doc or config changes.

---

## do

Implement the next planned task. Does **not** commit.

**Frontmatter:** `model: opus`

- Finds next planned task using `--include-planned`: first `[>]` with `plan:`, then first `[p]` with `plan:`, then first `[ ]` with `plan:`.
- Reads the plan file.
- Reads all files listed in `## Files` as initial context.
- **Staleness check:** reads the `started:` timestamp from the plan's YAML frontmatter and runs `git log --since=<started-timestamp> -- <file1> <file2> ...` for the listed files. If changes are found, re-reads affected files and revises plan steps before proceeding.
- Implements each `- [ ]` step. After completing each step, runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_complete.py <plan-file>` to mark it `[x]`.
- If a step fails: runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_block.py <plan-file> "<reason>"` to mark it `[!]`, then blocks the backlog task via `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_block.py doc/backlog.md "<reason>"`.
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

Generate a work-journal entry from recent git commits. Prints to stdout only — does not modify any files.

**Frontmatter:** `argument-hint: "<cutoff> [language-prefix] [guidance]"`

- **Cutoff (required):** ISO 8601 timestamp or natural-language date (e.g. `today`, `yesterday`, `2h ago`, `2026-03-01`). No default — the user must specify when to start from.
- **Language prefix (optional):** any recognizable prefix of a language name. Examples: `nor`, `no`, `norwegian`, `eng`, `en`, `english`, `fr`, `french`. Default: English.
- **Guidance (optional):** free-text for emphasis, length, or focus. Examples: `"Emphasize the refactoring work"`, `"3 sentences"`, `brief`, `detailed`.
- Arguments can appear in any order. Quoted strings are treated as guidance.
- Runs `git log --oneline --since=<cutoff>` to gather commits since the cutoff. When the cutoff is a bare date (e.g. `today` → `2026-03-08`), append ` 00:00:00` so git includes commits on that date.
- Generates plain narrative prose — dense, technical, work-journal style. No headings, no bullet points, no markdown formatting.
- Default length: 3-4 sentences. User can override with guidance like `detailed`, `brief`, or `5 sentences`.
- Start directly with the substance. No preamble like "Today's work...", "This session...", "The main focus was...".
- Write for a non-technical audience (CEO, stakeholders). Describe work in domain terms. No file paths, no variable/parameter names, no class names, no code references.
- Prints the entry to stdout. Does NOT read or write any files.
- Does NOT read `doc/changelog.md`.

---

## retry

Retry the first blocked task.

- Finds first `[!]` task with `plan:` sub-bullet in `doc/backlog.md`.
- Reads plan file, finds first `- [!]` step (or first `- [ ]` if no `[!]`).
- Implements remaining steps. After completing each step, runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_complete.py <plan-file>` to mark it `[x]`.
- If a step fails again: runs `python ${CLAUDE_PLUGIN_ROOT}/scripts/task_block.py <plan-file> "<reason>"` to mark it `[!]` and stays blocked.
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
                   adds plan: link         marks [x] via script
                   in backlog.md           runs build+test
                                                  │
                                           commit (manual)
                                           or auto in do-all
```
