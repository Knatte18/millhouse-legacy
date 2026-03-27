# Scripts Skill

> **Source of truth:** Scripts in `taskmill/scripts/` are the authoritative implementation. This file is reference documentation only.

Python scripts that operate on files with `- [ ]` checkbox format. Same scripts work for `_taskmill/backlog.md` and `.llm/plans/*.md`.

**Purpose:** Reduce token usage. CC does not read the entire file — it gets only the relevant extract via script output.

**Architecture:** Shared logic lives in `lib/` modules. Each CLI script is a thin wrapper that imports from `lib.*` and calls library functions. This ensures consistent behavior across all scripts.

---

## lib/ — shared modules

### lib/\_\_init\_\_.py

Empty file. Makes `lib/` a Python package so CLI scripts can `from lib.<module> import <function>`.

### lib/state.py

Constants and functions for checkbox state manipulation.

```python
CHECKBOX_RE = re.compile(r'^(\s*)- \[(.)\] ')
```

**`CHECKBOX_RE`** — line-start-anchored regex. Captures indent (group 1) and state character (group 2). All scripts use this single pattern; never define a local copy.

**State characters:** ` ` (unplanned), `>` (prioritized), `1`-`9` (in discussion), `p` (planned), `x` (done), `!` (blocked).

**`change_state(line, new_state) -> str`** — replace the state character in a checkbox line. Uses `re.sub(r'^(\s*- \[)[> p1-9!x](])', ...)` with the new state character injected via a lambda (to handle special regex characters like space). Returns the modified line. Raises `ValueError` if the line does not match `CHECKBOX_RE`.

**`is_incomplete(state) -> bool`** — returns `True` if state is in `(' ', '>', 'p')` or is a digit 1-9. Used by scripts that need to find actionable items.

### lib/parsing.py

Functions for finding and extracting tasks from checkbox files.

**`read_lines(path) -> list[str]`** — read a file and return `splitlines(keepends=True)`. Raises `FileNotFoundError` if the file does not exist.

**`find_task(lines, name=None, states=None, top_level_only=True, skip_claimed=False) -> int | None`** — find a task by priority or by name.

- If `name` is provided: case-insensitive substring match against checkbox lines. When `skip_claimed=True`, skips digit-state tasks (used by `task_claim.py` to avoid re-claiming). Returns first match index or `None`.
- If `name` is `None`: iterates through `states` list in order (e.g. `['>', ' ']`), returning the first top-level task matching each state before moving to the next.
- `top_level_only=True`: skip lines where indent (CHECKBOX_RE group 1) has length > 0.
- `top_level_only=False`: search all checkbox lines including indented sub-steps.

**`find_incomplete(lines) -> int | None`** — find the first incomplete item at any indent level. Iterates all lines, returns the index of the first checkbox whose state satisfies `is_incomplete()`, or `None`.

**`find_item_by_index(lines, index) -> int | None`** — find the Nth checkbox item (1-based) in the file. Counts all checkbox lines regardless of indent. Returns line index or `None`.

**`extract_block(lines, start) -> list[str]`** — return the task line at `start` plus all contiguous indented sub-bullets below it. A line is indented if it starts with `  ` (2 spaces) or `\t`. Blank lines within the block are skipped (not included in output). Stops at the first non-indented, non-blank line.

**`delete_block(lines, start) -> list[str]`** — remove the task line at `start`, all indented sub-bullets below it, and one trailing blank line (if present). Returns the modified lines list.

**`find_used_digits(lines) -> set[int]`** — scan all lines for checkbox states that are digits 1-9. Returns the set of digits in use.

**`find_lowest_unused_digit(used) -> int | None`** — returns the lowest digit 1-9 not in `used`, or `None` if all 9 slots are taken.

### lib/subbullet.py

Functions for manipulating sub-bullets on checkbox items.

**`upsert_subbullet(lines, idx, key, value) -> str`** — add or update a `  - <key>: <value>\n` sub-bullet on the item at line `idx`.

1. Scan lines below `idx` that are part of the sub-bullet block (indented with `  ` or `\t`; stop at blank or non-indented line).
2. If a sub-bullet matching `^\s*-\s+<key>:` exists, update it in place.
3. If no match, insert the new sub-bullet at the **end** of the sub-bullet block (before the first non-indented or blank line after the block).
4. Return the formatted sub-bullet string.

This is the **only** function that inserts sub-bullets. All scripts must use it — never insert sub-bullets with manual `lines.insert()`.

### lib/locking.py

File locking for concurrent access to `backlog.md`.

**`get_lock(file_path) -> FileLock | None`** — if `Path(file_path).name == 'backlog.md'`, create `.llm/` directory if needed and return `filelock.FileLock('.llm/backlog.lock', timeout=5)`. Otherwise return `None`.

**`locked(file_path)`** — context manager that acquires the lock (if any) on entry and releases on exit. Usage: `with locked(file_path): ...`. This is the preferred interface; all CLI scripts use it instead of manual acquire/release.

### lib/io.py

File I/O helpers.

**`write_file(path, lines, normalize=False)`** — join lines into a string, optionally run `normalize_backlog()` if `normalize=True`, then write to `path` with UTF-8 encoding.

**`is_backlog(path) -> bool`** — returns `True` if `Path(path).name == 'backlog.md'`.

### lib/backlog_format.py

Shared normalization for `_taskmill/backlog.md` formatting. Moved from top-level `backlog_format.py`.

**`normalize_backlog(text: str) -> str`** — normalize backlog content.

Normalization rules:
1. Ensure the file starts with `# Backlog\n\n`. If the header is missing, prepend it. If a different `# ...` header exists on line 1, replace it.
2. Ensure a blank line before each top-level checkbox (matched by `^- \[.\] `, no leading indent).
3. Collapse consecutive blank lines into exactly one.
4. Ensure a single trailing newline (no trailing blank lines).

Not used for plan files or other checkbox files — backlog only.

### lib/frontmatter.py

YAML frontmatter parsing for plan files.

**`find_frontmatter(lines) -> tuple[int, int] | None`** — find the opening `---` (must be line 0) and closing `---` delimiter. Returns `(start, end)` indices or `None` if no valid frontmatter.

**`upsert_frontmatter_key(lines, key, value) -> str`** — find or insert a `<key>: <value>` line within the YAML frontmatter block. If the key already exists, update it. If not, insert before the closing `---`. Returns the formatted line. Raises `ValueError` if no frontmatter found.

---

## CLI scripts

Each script is a thin wrapper. It parses CLI arguments, calls library functions, and prints output. All scripts follow this pattern:

1. Parse arguments (argparse or sys.argv).
2. Use `with locked(file_path):` for concurrency safety.
3. Call `read_lines()` to get file content.
4. Call library functions to find/modify tasks.
5. Call `write_file()` to persist changes (with `normalize=is_backlog(path)`).
6. Print result to stdout. Exit 0 on success, 1 on failure (with message to stderr).

### task_get.py

Extract the next incomplete task/step with its context lines.

```
Usage: task_get.py [--include-planned] <file-path>
```

Selection priority (default): calls `find_task(lines, states=['>', ' '])`.

With `--include-planned`: calls `find_task(lines, states=['>', 'p', ' '])`.

`[N]` tasks (any digit 1-9) are always skipped — they are claimed by another thread. This is handled by `find_task` which skips digit-state items when searching by state priority.

Output: calls `extract_block()` and prints the result. Exit code 0 if found, 1 if no incomplete items.

Read-only — does not modify the file.

---

### task_add.py

Append a new item to a file.

```
Usage: task_add.py <file-path> <Title: description>
```

If the input contains a colon, the part before becomes a bold title and the part after becomes an indented description. If no colon, the entire input becomes the bold title with no description. Appends the entry followed by a trailing blank line. Creates the file if it doesn't exist.

Uses `write_file()` with `normalize=is_backlog(path)`.

---

### task_complete.py

Mark an incomplete item as done, or delete it.

```
Usage: task_complete.py [--delete] <file-path> [task-name]
```

If `task-name` provided: calls `find_task(lines, name=task_name, top_level_only=False)` — case-insensitive substring match at any indent level.

If no name: calls `find_task(lines, states=[' ', '>', 'p'], top_level_only=False)` — finds the first incomplete item by state priority.

Default: calls `change_state(line, 'x')` to mark done.

With `--delete`: calls `delete_block()` to remove the entry entirely. Used for backlog tasks where `_taskmill/changelog.md` already records the completion.

Prints the matched item. Exit code 0 if found, 1 if no incomplete items.

---

### task_block.py

Mark an incomplete item as blocked.

```
Usage: task_block.py [--name TASK-NAME] <file-path> [reason]
```

If `--name` provided: calls `find_task(lines, name=task_name, top_level_only=False)` — case-insensitive substring match at any indent level.

If no name: calls `find_task(lines, states=[' ', '>', 'p'], top_level_only=False)` — finds the first incomplete item by state priority.

Calls `change_state(line, '!')` to mark blocked.

If reason provided: calls `upsert_subbullet(lines, idx, 'blocked', reason)` to add or update the blocked reason. This ensures consistent sub-bullet placement at the end of the sub-bullet block.

Prints the modified task line. Exit code 0 if found, 1 if no incomplete items.

---

### task_subbullet.py

Add or update a sub-bullet on a checkbox item.

```
Usage: task_subbullet.py <file-path> <identifier> "<key>: <value>"
```

Identifier auto-detection:
- If numeric (e.g. `3`): calls `find_item_by_index(lines, int(identifier))`.
- Otherwise: calls `find_task(lines, name=identifier, top_level_only=False)` — searches all checkbox lines including indented sub-steps.

Calls `upsert_subbullet(lines, idx, key, value)`.

Output: the updated sub-bullet line. Exit code 0 on success, 1 if item not found.

---

### task_claim.py

Claim a task for discussion by assigning it a thread number and recording the start time.

```
Usage: task_claim.py <file-path> [task-name]
```

If `task-name` provided: calls `find_task(lines, name=task_name, skip_claimed=True)` (top-level only, skips already-claimed digit tasks).

If no name: calls `find_task(lines, states=['>', ' '])` (same priority as `task_get.py`).

Calls `find_used_digits(lines)` then `find_lowest_unused_digit(used)` to get the next available thread number. Calls `change_state(line, str(digit))` to claim.

Calls `upsert_subbullet(lines, idx, 'started', <ISO 8601 UTC timestamp>)`.

Output: the claimed task line. Exit code 0 if claimed, 1 if no eligible task or all 9 slots full.

---

### task_plan.py

Mark a task as planned and link its plan file.

```
Usage: task_plan.py [--state STATE] <file-path> <task-name> <plan-path>
```

Calls `find_task(lines, name=task_name)` (top-level only).

Changes state to `--state` value (default: `p`). Accepts any single character including space. Calls `change_state(line, state)`.

Calls `upsert_subbullet(lines, idx, 'plan', plan_path)`.

Output: the updated task line. Exit code 0 on success, 1 if task not found.

---

### plan_finish.py

Set the `finished:` timestamp in a plan file's YAML frontmatter.

```
Usage: plan_finish.py <plan-file>
```

Calls `find_frontmatter(lines)` to locate the YAML block. Calls `upsert_frontmatter_key(lines, 'finished', <ISO 8601 UTC timestamp>)`.

No file locking (plan files are single-thread).

Output: the updated `finished:` line. Exit code 0 on success, 1 if file not found or no frontmatter.
