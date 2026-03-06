# Changelog

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
