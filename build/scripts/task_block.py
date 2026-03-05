"""Mark the first incomplete item as blocked.

Usage: task_block.py <file-path> [reason]

Finds first [ ], [>], or [p] item and replaces with [!].
Optionally inserts a `blocked: <reason>` sub-bullet.
Exit code 0 if found, 1 if no incomplete items.
"""

import re
import sys
from pathlib import Path

from task_lock import lock_backlog

CHECKBOX_PATTERN = re.compile(r"^(\s*- \[)([ >p1-9])(\] )")


def main():
    if len(sys.argv) < 2:
        print("Usage: task_block.py <file-path> [reason]", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    reason = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None

    with lock_backlog(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(f"File not found: {file_path}", file=sys.stderr)
            sys.exit(1)

        for i, line in enumerate(lines):
            match = CHECKBOX_PATTERN.match(line)
            if match:
                blocked_line = CHECKBOX_PATTERN.sub(r"\1!\3", line)
                lines[i] = blocked_line

                if reason:
                    task_indent = len(line) - len(line.lstrip())
                    sub_indent = " " * (task_indent + 2)
                    reason_line = f"{sub_indent}- blocked: {reason}\n"
                    lines.insert(i + 1, reason_line)

                with open(file_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                print(f"Blocked: {blocked_line.strip()}")
                if reason:
                    print(f"Reason: {reason}")
                sys.exit(0)

    print("No incomplete items found.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
