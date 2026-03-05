"""Mark the first incomplete item as done.

Usage: task_complete.py [--delete] <file-path>

Finds first [ ], [>], or [p] item and replaces with [x].
Prints the completed item.
Exit code 0 if found, 1 if no incomplete items.

With --delete: instead of marking [x], deletes the matched entry entirely
(the task line, all indented sub-bullets below it, and any trailing blank line).
Used for backlog tasks where doc/changelog.md already records the completion.
"""

import re
import sys
from pathlib import Path

from task_lock import lock_backlog

CHECKBOX_PATTERN = re.compile(r"^(\s*- \[)([ >p1-9])(\] )")


def main():
    args = sys.argv[1:]
    delete_mode = False

    if "--delete" in args:
        delete_mode = True
        args.remove("--delete")

    if len(args) < 1:
        print("Usage: task_complete.py [--delete] <file-path>", file=sys.stderr)
        sys.exit(1)

    file_path = args[0]

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
                if delete_mode:
                    task_indent = len(line) - len(line.lstrip())
                    end = i + 1
                    while end < len(lines):
                        subsequent = lines[end]
                        if subsequent.strip() == "":
                            end += 1
                            break
                        subsequent_indent = len(subsequent) - len(subsequent.lstrip())
                        if subsequent_indent > task_indent:
                            end += 1
                        else:
                            break
                    deleted_line = line.strip()
                    del lines[i:end]
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    print(f"Deleted: {deleted_line}")
                else:
                    completed_line = CHECKBOX_PATTERN.sub(r"\1x\3", line)
                    lines[i] = completed_line
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    print(f"Completed: {completed_line.strip()}")
                sys.exit(0)

    print("No incomplete items found.", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
