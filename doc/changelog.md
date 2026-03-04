# Changelog

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
