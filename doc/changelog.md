# Changelog

## 2026-03-15 **Required task_name for backlog mutations**
- `task_complete.py`, `task_block.py`, `task_unblock.py` now exit with an error when operating on `backlog.md` without a task name
- Plan files retain implicit "find first incomplete" behavior
- Updated `mill-do` and `mill-retry` skill instructions to pass task name
- Added tests for all three scripts

## 2026-03-14 **Added requirements.txt for plugin Python dependencies**
- Created `taskmill/requirements.txt` with `filelock` as declared dependency
- Updated deploy skill to run `pip install -r` after plugin installation
- Added Python and pip as prerequisites in `INSTALL.md`

## 2026-03-13 **Added task_unblock.py and blocked-item completion**
- Created `task_unblock.py`: transitions `[!]` → `[ ]` and removes the `blocked:` sub-bullet
- Added `remove_subbullet(lines, idx, key)` to `lib/subbullet.py`
- Updated `task_complete.py` no-name states from `[' ', '>', 'p']` to `[' ', '>', 'p', '!']` (blocked items completed last)
- Added test suite: `test_subbullet.py` (6 tests), `test_unblock.py` (4 tests), `test_complete.py` (3 tests)

## 2026-03-13 **Updated doc/ reference files after build elimination**
- Added `find_incomplete()` documentation to `skill-scripts.md` (was missing from `lib/parsing.py` section)
- Fixed `change_state()` regex in `skill-scripts.md` to match actual implementation: `[> p1-9!x]` (was `[> p1-9!]`)
- Fixed duplicate `p` in `change_state()` regex in `lib/state.py`: `[> p1-9!xp]` → `[> p1-9!x]`

## 2026-03-13 **Eliminated build step, restructured to taskmill/ as source of truth**
- Moved `build/taskmill/` to `taskmill/` at repo root — skills and scripts are now edited directly
- Deleted `BUILD.md`, `.claude/commands/mill-build.md`, and `.claude/commands/mill-deploy.md`
- Created repo-local skill `.claude/skills/taskmill-deploy/SKILL.md` replacing the old build+deploy commands
- Deleted 29 `doc/**/skill-*.md` spec files (kept `skill-commands.md` and `skill-scripts.md` as reference docs)
- Updated `marketplace.json`, `CLAUDE.md`, `INSTALL.md`, and reference docs to reflect the new structure

## 2026-03-12 **Added task-name targeting to task_complete.py and task_block.py**
- `task_complete.py` now accepts an optional `task_name` positional argument for case-insensitive substring matching via `find_task(name=...)`
- `task_block.py` now accepts `--name` flag for the same targeting
- Without a name, both scripts use `find_task(states=[' ', '>', 'p'])` state-priority search (fixes discrepancy where code used `find_incomplete()` instead)
- Fixes bug where `--delete` could not target `[p]` tasks and would delete unrelated `[ ]` tasks first

## 2026-03-12 **Renamed all skills to mill- prefix**
- Added `mill-` prefix to all 29 skill `name:` fields to avoid Claude Code short-alias collisions (e.g. `/commit` → `/mill-commit`)
- Updated BUILD.md mapping: `skill-<name>.md` → `build/taskmill/skills/mill-<name>/SKILL.md`
- Updated all `@taskmill:` cross-references across 14 skill files to use `mill-` prefix
- Updated `~/.claude/CLAUDE.md` startup references to `taskmill:mill-conversation`, `taskmill:mill-llm-context`, `taskmill:mill-workflow`

## 2026-03-12 **Converted commands to verbatim-copied skills**
- Created 14 skill source files in `doc/taskflow/commands/` (one per command), replacing LLM-generated command files that drifted on each rebuild
- Replaced `${CLAUDE_PLUGIN_ROOT}` with `${CLAUDE_SKILL_DIR}/../..` in all script paths (skills use a different variable)
- Combined skills (`do-commit`, `do-all`, `finalize-do*`) inline all steps for self-contained execution
- Updated `BUILD.md`: removed Commands section, added command-skills to verbatim-copy pipeline
- Marked `skill-commands.md` as human-readable reference (no longer drives the build)
- Build output changes from `commands/*.md` to `skills/<name>/SKILL.md` for these files

## 2026-03-12 **Fixed find_task skipping digit-state tasks in name-based search**
- Added `skip_claimed` parameter to `find_task()` in `lib/parsing.py` (default `False`)
- Name-based search now finds tasks in digit states (`[1]`-`[9]`) by default, fixing `task_plan.py` and `task_subbullet.py` which need to operate on claimed tasks
- `task_claim.py` passes `skip_claimed=True` to preserve correct behavior: don't re-claim already-claimed tasks
- State-priority search (no name given) unchanged — still skips digit-state tasks unconditionally

## 2026-03-11 **Revised backlog/plan scripts with shared library architecture**
- Replaced monolithic per-script implementations with a `lib/` package: `state.py`, `parsing.py`, `subbullet.py`, `locking.py`, `io.py`, `backlog_format.py`, `frontmatter.py`
- Each CLI script is now a thin wrapper importing from `lib.*`
- Unified task-finding logic via `find_task()` with configurable `top_level_only` and state priority
- Standardized state changes through single `change_state()` function with correct regex (fixed duplicate `p` in character class)
- Centralized sub-bullet insertion: `task_block.py` now uses `upsert_subbullet()` instead of manual `lines.insert()`
- Centralized locking via `lib/locking.py` context manager; deleted unused `task_lock.py`
- Updated `skill-scripts.md` spec and `BUILD.md` to document new architecture

## 2026-03-11 **Added backlog formatting normalization**
- Created `backlog_format.py` with `normalize_backlog()`: ensures `# Backlog` header, one blank line between task entries, single trailing newline
- Integrated into all six mutating scripts (`task_add`, `task_complete`, `task_block`, `task_claim`, `task_plan`, `task_subbullet`)
- Added spec section to `skill-scripts.md`

## 2026-03-11 **Fixed task_complete.py and task_block.py to match claimed [N] tasks**
- Updated `find_incomplete()` in `task_complete.py` and the equivalent check in `task_block.py` to include digits 1-9 in the state match
- Updated spec in `skill-scripts.md` to document the corrected behavior

## 2026-03-11 **Added park flag to finalize command**
- Added `--state` argument to `task_plan.py` (default `p`), replacing the hardcoded `[p]` substitution with a configurable state character
- Added `--park` flag to `finalize` command: passes `--state ' '` to set the task back to `[ ]` while preserving the `plan:` sub-bullet
- Added incomplete discussion guard: prompts user to choose between full finalize or park when steps are incomplete
- Updated formats skill to document parked state (`[ ]` with `plan:` sub-bullet)

## 2026-03-11 **Enforced script-only mutations for plan files**
- Created `task_subbullet.py`: generic script for adding/updating sub-bullets on checkbox items, with auto-detect by index (numeric) or name (substring match); exposes `upsert_subbullet()` for import
- Created `plan_finish.py`: sets `finished:` timestamp in plan YAML frontmatter
- Refactored `task_claim.py` and `task_plan.py` to import `upsert_subbullet` instead of inline insertion logic
- Replaced `validate-backlog.sh` with `validate-protected-files.sh`: blocks Edit/Write on both `backlog.md` and `.llm/plans/*.md` (Write allowed for plan creation when file doesn't exist)
- Updated all `do*`, `retry` commands to call `task_complete.py`/`task_block.py` on plan files instead of direct Edit
- Updated workflow and formats skills with plan file mutation rules and script tables

## 2026-03-08 **Added git guard hook**
- Created `validate-git.sh` PreToolUse hook that blocks dangerous git commands via JSON decisions
- `deny` for `git add -A/--all`, `git commit -a`, `git push --force/-f`
- `ask` for `git reset --hard` and `git clean -fd` (user can approve when intentional)
- Added Bash matcher to hooks.json with 500ms timeout

## 2026-03-08 **Added language-agnostic testing skill**
- Created base `testing` skill with universal principles: strict assertions, mock discipline (terminology: mock vs fake vs stub), naming conventions, record/replay preference
- Updated `csharp-testing` and `python-testing` to reference `@taskmill:testing` instead of repeating general principles
- Added `@taskmill:testing` to workflow skill invocation table

## 2026-03-08 **Revised log command to use git commits only**
- Removed changelog.md dependency: no longer reads changelog for cutoff detection or tone matching
- Made cutoff argument required (e.g. `today`, `yesterday`, `2h ago`)
- Changed output to plain narrative prose with no headings, no bullet points, no markdown
- Added language prefix support (e.g. `nor`, `en`, `fr`) and free-text guidance for emphasis/length

## 2026-03-08 **Revised plan step format for better granularity and mandatory tests**
- Added step-writing rules to `finalize` command: one step per file, explicit file paths and function/class names, no compound steps
- Added mandatory test steps: plans must include test steps when `## Files` contains source code files
- Replaced minimal plan example in `skill-formats.md` with a detailed example showing per-file steps and test steps
- Updated `finalize.md`, `finalize-do.md`, and `finalize-do-commit.md` build outputs with the new guidance

## 2026-03-08 **Added Python skills and language-agnostic build routing**
- Created `python-build` skill: `ruff check .` + `pytest` as mandatory build commands
- Created `python-comments` skill: module docstrings required, concise function docstrings, no Args/Returns sections, imperative inline comments
- Created `python-testing` skill: pytest conventions with fixtures, parametrize, strict assertions
- Made workflow skill language-agnostic: added Language Detection section with marker-file table (`pyproject.toml` → Python, `.csproj` → C#)
- Updated `do` command to route to the detected language's build skill instead of hardcoding `@taskmill:csharp-build`
- Updated BUILD.md result tree with new `python-*` skill entries

## 2026-03-07 **Added finalize-do, finalize-do-commit, finalize-do-all commands**
- Three new commands combine finalization with immediate implementation, eliminating the manual two-step process
- `finalize-do`: finalize + implement, no commit
- `finalize-do-commit`: finalize + implement + commit (refuses on main without `--onmain`)
- `finalize-do-all`: finalize + implement all planned tasks committing after each
- Changed `model: sonnet` to `model: opus` in do, do-commit, do-all commands

## 2026-03-07 **Added add-discuss command**
- New command adds a task to the backlog via `task_add.py`, claims it via `task_claim.py`, then proceeds with the standard discuss flow

## 2026-03-07 **Simplified backlog task handling**
- Added `task_plan.py` script: marks a task `[p]` and adds/replaces `plan:` sub-bullet using filelock; used by `finalize` command instead of direct Edit on backlog.md
- Added `validate-backlog.sh` PreToolUse hook: reads tool input JSON from stdin, blocks Edit/Write calls targeting `backlog.md`
- Added `hooks/hooks.json` with PreToolUse entries for Edit and Write matchers
- Updated `finalize` command to use `task_plan.py` instead of direct backlog edits
- Added explicit "never Edit/Write backlog.md" rule to `formats` and `workflow` skills
- Extended `BUILD.md` to describe hooks/ output directory

## 2026-03-07 **Revised git and workflow skills**
- Replaced blanket "never operate on main" rule with nuanced branch policy: never switch TO main, can create new branches, committing on main requires `--onmain` override
- Added `do-commit` command: checks branch, prompts to create new branch if on main, then implements next planned task and commits
- Simplified `do-all` to loop `do-commit` with upfront branch check
- Updated `commit` command with `--onmain` flag support and refusal behavior
- Regenerated affected build outputs: `git/SKILL.md`, `commit.md`, `do-commit.md`, `do-all.md`

## 2026-03-06 **Shortened plugin command names**
- Dropped `task-`/`mill-` prefixes from all plugin commands — now invoked as `/taskmill.discuss`, `/taskmill.finalize`, `/taskmill.do`, `/taskmill.do-all`, `/taskmill.list`, `/taskmill.add`, `/taskmill.retry`, `/taskmill.commit`, `/taskmill.log`
- `task-plan` renamed to `finalize` (more descriptive of what it does)
- `mill-commit` and `mill-logentry` renamed to `commit` and `log`
- Updated `skill-commands.md` section headings, cross-references, and workflow diagram
- Updated `skill-formats.md` command name references and plan step rules example
- Updated `BUILD.md` section pattern description and result listing
- Regenerated all 9 command files in `build/taskmill/commands/` with new names

## 2026-03-05 **New command: mill-logentry**
- Added `mill-logentry` command that generates a changelog entry from recent git commits and prints to stdout
- Accepts optional cutoff time, language, and length/emphasis arguments
- Auto-detects cutoff from newest changelog heading if not specified
- Added spec section to `doc/taskflow/skill-commands.md`, built and deployed to `~/.claude/commands/`

## 2026-03-05 **Fixed build reference in plan steps**
- Changed plan step example from nonexistent `python scripts/build_skills.py` to `Regenerate build output following BUILD.md`
- Updated doc/taskflow/skill-formats.md, doc/taskflow/skill-commands.md, and corresponding build outputs

## 2026-03-05 **Staleness check uses discussion start time**
- Added `[N]` state (digit 1-9) for tasks claimed by a discussion thread
- Added `started:` sub-bullet to backlog tasks, written when discussion begins via `hanf-discuss-task`
- Added `started:` and `finished:` YAML frontmatter to plan files
- Staleness check now uses `started:` from plan frontmatter instead of filename timestamp, catching changes during discussion phase
- Created `hanf_task_claim.py` script for atomically claiming tasks with thread numbers
- Added `model: sonnet` frontmatter to `hanf-do-planned-task` and `hanf-do-all-planned` commands
- Updated `hanf-list-tasks` to show `[N]` (in discussion) state group
- Updated checkbox regex in `hanf_task_complete.py` and `hanf_task_block.py` to handle digit states

## 2026-03-05 **Multi-threaded planning support**
- Changed plan timestamps from `YYYY-MM-DD-HHMM` to `YYYY-MM-DD-HHMMSS` for second-level precision
- Added `## Files` section to plan format for listing files the plan expects to modify
- Added staleness check to `hanf-do-planned-task` and `hanf-do-all-planned`: checks `git log` against plan timestamp and file list before implementing
- Added file locking (`.llm/backlog.lock`) to all task scripts to prevent concurrent `backlog.md` corruption
- Created `hanf_lock.py` shared locking module
- Renamed existing plan files to use HHMMSS format
- Updated all doc specs, rebuilt all skills, commands, and scripts

## 2026-03-05 **Incremental skill build**
- `hanf-skill-build` now defaults to incremental mode using `git diff --name-only HEAD -- doc/` to detect changed sources
- Added `full` argument for complete clean + rebuild
- Added "discussion only" rule to `hanf-discuss-task` to prevent auto-entering plan mode
- Updated BUILD.md to document incremental behavior

## 2026-03-05 **Plan steps must not use slash command syntax**
- Added "Plan step rules" to plan format spec in skill-formats.md
- Added guidance to hanf-finalize-plan in skill-commands.md
- Steps must describe concrete actions, not reference `/hanf-*` commands or `~/.claude/skills/` files

## 2026-03-04 **Added UTC clock time to plan filenames**
- Changed plan naming from `YYYY-MM-DD-<slug>.md` to `YYYY-MM-DD-HHMM-<slug>.md` (UTC)
- Updated skill-llm-context.md, skill-commands.md, skill-formats.md
- Renamed 8 existing plan files with incrementing time components
- Rebuilt all skills, commands, and scripts

## 2026-03-04 **Cleaned up backlog: delete completed tasks instead of marking [x]**
- Added `--delete` flag to `hanf_task_complete.py` — deletes matched entry (line + sub-bullets + trailing blank) instead of marking `[x]`
- Updated `hanf-do-planned-task`, `hanf-do-all-planned`, `hanf-retry-blocked` to use `--delete` for backlog operations
- Removed "done" count from `hanf-list-tasks` status summary
- Removed `[x]` state from backlog example and state table in `skill-formats.md`; noted that `[x]` is only for plan files
- Updated `skill-workflow.md` task completion step to say "task entry deleted"
- Removed pre-existing `[x]` entry from backlog

## 2026-03-04 **Fixed checkbox matching in task scripts**
- Replaced substring matching (`marker in line`) with line-start-anchored regex (`r'^\s*- \[(.)\] '`)
- Uses `re.sub` for state replacement instead of `str.replace()` to avoid modifying bracket patterns in title text
- Added "Checkbox matching" section to `doc/taskflow/skill-scripts.md` as the behavioral spec
- Affected scripts: hanf_task_get.py, hanf_task_complete.py, hanf_task_block.py

## 2026-03-04 **Added [p] planned state and updated task commands**
- Added `[p]` (planned) task state to skill-formats.md and skill-llm-context.md
- Added `--include-planned` flag to hanf_task_get.py for prioritized → planned → unplanned selection
- Updated hanf_task_complete.py and hanf_task_block.py to handle `[p]` state
- Updated hanf-finalize-plan to set task state to `[p]` after creating a plan
- Updated hanf-discuss-task to summarize existing plans when a task has one
- Updated hanf-do-planned-task and hanf-do-all-planned to use `--include-planned`
- Updated hanf-list-tasks to group tasks by `[>]`, `[p]`, `[ ]`, `[!]` states

## 2026-03-04 **Restructured changelog format**
- Each entry gets its own `## YYYY-MM-DD **Title**` heading (no shared date headings)
- Updated skill-formats.md changelog example and description
- Reformatted existing changelog entries to new style
- Rebuilt and deployed all skills

## 2026-03-04 **Restructured backlog format**
- Bold titles, optional indented descriptions, blank lines between entries
- Updated skill-formats.md backlog example
- Updated hanf_task_add.py to parse `Title: description` colon delimiter
- Updated hanf-add-task command and skill-commands.md
- Reformatted all existing backlog entries to new format

## 2026-03-04 **Updated plan file naming convention**
- Changed to YYYY-MM-DD-<slug>.md format
- Updated skill-formats.md, skill-commands.md, skill-llm-context.md (doc/ and build/)
- Updated hanf-finalize-plan and hanf-add-task commands

## 2026-03-04 **Restructured repo**
- Moved spec files (core/, coding/, git/, taskflow/) into doc/
- Renamed INSTALL.md to BUILD.md with updated paths targeting build/ directory
- Updated README.md links with doc/ prefix
- Created build/ directory with generated skills, commands, scripts, and CLAUDE.md
- Added repo-local commands: hanf-skill-build (generates into build/) and hanf-skill-deploy (copies to ~/.claude/)
- Created doc/changelog.md
