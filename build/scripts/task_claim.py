"""Claim a task for discussion by assigning a thread number and recording start time.

Usage: task_claim.py <file-path> [task-name]

Finds the target task (by name if provided, otherwise first [>], then first [ ]).
Changes its state to [N] where N is the lowest unused digit (1-9).
Adds a `started: <ISO 8601 UTC timestamp>` sub-bullet.

Output: the claimed task line. Exit code 0 if claimed, 1 if no eligible task found.
"""

import re
import sys
from datetime import datetime, timezone

from task_lock import lock_backlog

CHECKBOX_PATTERN = re.compile(r"^(\s*- \[)(.)(\] )")


def find_used_numbers(lines):
    """Find all digit states currently in use."""
    used = set()
    for line in lines:
        match = CHECKBOX_PATTERN.match(line)
        if match and match.group(2).isdigit():
            used.add(int(match.group(2)))
    return used


def next_available_number(used):
    """Return the lowest unused digit 1-9."""
    for n in range(1, 10):
        if n not in used:
            return n
    return None


def find_task_index(lines, task_name=None):
    """Find the index of the target task line."""
    if task_name:
        for i, line in enumerate(lines):
            match = CHECKBOX_PATTERN.match(line)
            if match and match.group(2) in (" ", ">") and task_name.lower() in line.lower():
                return i
        return None

    # Default priority: first [>], then first [ ]
    for state in (">", " "):
        for i, line in enumerate(lines):
            match = CHECKBOX_PATTERN.match(line)
            if match and match.group(2) == state:
                return i
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: task_claim.py <file-path> [task-name]", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    task_name = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None

    with lock_backlog(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(f"File not found: {file_path}", file=sys.stderr)
            sys.exit(1)

        task_index = find_task_index(lines, task_name)
        if task_index is None:
            print("No eligible task found.", file=sys.stderr)
            sys.exit(1)

        used = find_used_numbers(lines)
        number = next_available_number(used)
        if number is None:
            print("All thread numbers 1-9 are in use.", file=sys.stderr)
            sys.exit(1)

        # Replace state with the assigned number
        line = lines[task_index]
        claimed_line = CHECKBOX_PATTERN.sub(rf"\g<1>{number}\3", line)
        lines[task_index] = claimed_line

        # Find insertion point for started: sub-bullet (after task line and existing sub-bullets)
        task_indent = len(line) - len(line.lstrip())
        insert_at = task_index + 1
        while insert_at < len(lines):
            subsequent = lines[insert_at]
            if subsequent.strip() == "":
                break
            subsequent_indent = len(subsequent) - len(subsequent.lstrip())
            if subsequent_indent > task_indent:
                insert_at += 1
            else:
                break

        # Add started: sub-bullet
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        sub_indent = " " * (task_indent + 2)
        started_line = f"{sub_indent}- started: {now}\n"
        lines.insert(insert_at, started_line)

        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        print(f"Claimed: {claimed_line.strip()}")


if __name__ == "__main__":
    main()
