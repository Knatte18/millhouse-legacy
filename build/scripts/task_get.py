"""Extract the next incomplete task/step with its context lines.

Usage: task_get.py [--include-planned] <file-path>

Selection priority (default):
1. First [>] (prioritized) item
2. First [ ] (unplanned/undone) item

With --include-planned:
1. First [>] (prioritized) item
2. First [p] (planned) item
3. First [ ] (unplanned/undone) item

Output: the task line and all indented sub-bullets below it.
Exit code 0 if found, 1 if no incomplete items.
"""

import re
import sys
from pathlib import Path

from task_lock import lock_backlog

CHECKBOX_PATTERN = re.compile(r"^(\s*- \[)(.)(\] )")


def main():
    args = sys.argv[1:]
    include_planned = False

    if "--include-planned" in args:
        include_planned = True
        args.remove("--include-planned")

    if len(args) < 1:
        print("Usage: task_get.py [--include-planned] <file-path>", file=sys.stderr)
        sys.exit(1)

    file_path = args[0]

    with lock_backlog(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(f"File not found: {file_path}", file=sys.stderr)
            sys.exit(1)

    prioritized_match = find_task(lines, ">")
    if prioritized_match is not None:
        print(prioritized_match)
        sys.exit(0)

    if include_planned:
        planned_match = find_task(lines, "p")
        if planned_match is not None:
            print(planned_match)
            sys.exit(0)

    unplanned_match = find_task(lines, " ")
    if unplanned_match is not None:
        print(unplanned_match)
        sys.exit(0)

    print("No incomplete items found.", file=sys.stderr)
    sys.exit(1)


def find_task(lines, state_character):
    """Find the first line with a checkbox matching the given state character."""
    for i, line in enumerate(lines):
        match = CHECKBOX_PATTERN.match(line)
        if match and match.group(2) == state_character:
            result = [line.rstrip()]
            task_indent = len(line) - len(line.lstrip())
            for j in range(i + 1, len(lines)):
                subsequent = lines[j]
                if subsequent.strip() == "":
                    break
                subsequent_indent = len(subsequent) - len(subsequent.lstrip())
                if subsequent_indent > task_indent:
                    result.append(subsequent.rstrip())
                else:
                    break
            return "\n".join(result)
    return None


if __name__ == "__main__":
    main()
