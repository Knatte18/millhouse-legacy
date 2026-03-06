# Scripts Skill

Python scripts that operate on files with `- [ ]` checkbox format. Same scripts work for `doc/backlog.md` and `.llm/plans/*.md`.

**Purpose:** Reduce token usage. CC does not read the entire file — it gets only the relevant extract via script output.

---

## task_get.py

Extract the next incomplete task/step with its context lines.

```
Usage: task_get.py [--include-planned] <file-path>
```

Selection priority (default):
1. First `[>]` (prioritized) item
2. First `[ ]` (unplanned/undone) item

With `--include-planned`:
1. First `[>]` (prioritized) item
2. First `[p]` (planned) item
3. First `[ ]` (unplanned/undone) item

`[N]` tasks (any digit 1-9) are always skipped — they are claimed by another thread.

Output: the task line and all indented sub-bullets below it. Exit code 0 if found, 1 if no incomplete items.

---

## task_add.py

Append a new item to a file.

```
Usage: task_add.py <file-path> <Title: description>
```

If the input contains a colon, the part before becomes a bold title and the part after becomes an indented description. If no colon, the entire input becomes the bold title with no description. Appends the entry followed by a trailing blank line. Creates the file if it doesn't exist.

---

## task_complete.py

Mark the first incomplete item as done.

```
Usage: task_complete.py [--delete] <file-path>
```

Finds first `[ ]`, `[>]`, or `[p]` item and replaces with `[x]`. Prints the completed item. Exit code 0 if found, 1 if no incomplete items.

With `--delete`: instead of marking `[x]`, deletes the matched entry entirely (the task line, all indented sub-bullets below it, and any trailing blank line). Used for backlog tasks where `doc/changelog.md` already records the completion.

---

## task_block.py

Mark the first incomplete item as blocked.

```
Usage: task_block.py <file-path> [reason]
```

Finds first `[ ]`, `[>]`, or `[p]` item and replaces with `[!]`. Optionally inserts a `blocked: <reason>` sub-bullet. Exit code 0 if found, 1 if no incomplete items.

---

## File locking

All task scripts that read or write `doc/backlog.md` acquire `.llm/backlog.lock` before operating. This prevents concurrent CC threads from corrupting the file when planning tasks in parallel.

- Lock is acquired with a short timeout (5 seconds). If the lock cannot be acquired, the script exits with an error.
- Lock is released automatically when the script completes.
- Lock file location: `.llm/backlog.lock` (relative to project root, inside the untracked `.llm/` directory).

Scripts affected: `task_get.py`, `task_add.py`, `task_complete.py`, `task_block.py`, `task_claim.py`.

---

## Checkbox matching

All scripts that search for or replace checkbox states **must** use line-start-anchored regex to avoid false matches when bracket patterns like `[p]` or `[x]` appear inside task title text.

**Detection pattern:** `r'^\s*- \[(.)\] '` — matches a checkbox only at line start (with optional leading whitespace for indented plan sub-steps). The capture group yields the state character.

**State characters:** ` ` (unplanned), `>` (prioritized), `1`-`9` (in discussion), `p` (planned), `x` (done), `!` (blocked).

**Replacement:** Use `re.sub(r'^(\s*- \[)[>p 1-9](])' , r'\1x\2', line)` (or the appropriate target state) instead of `str.replace()`. This ensures only the leading checkbox is modified, never bracket text in titles.

Scripts affected: `task_get.py`, `task_complete.py`, `task_block.py`. `task_add.py` only appends and is unaffected.

---

## task_claim.py

Claim a task for discussion by assigning it a thread number and recording the start time.

```
Usage: task_claim.py <file-path> [task-name]
```

Finds the target task (by name if provided, otherwise first `[>]`, then first `[ ]` — same as `task_get.py` default priority). Changes its state to `[N]` where N is the lowest unused digit (1-9) among current `[N]` states in the file. Adds a `started: <ISO 8601 UTC timestamp>` sub-bullet to the task.

Output: the claimed task line. Exit code 0 if claimed, 1 if no eligible task found.
