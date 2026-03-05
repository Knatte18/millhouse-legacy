"""Append a new item to a file.

Usage: task_add.py <file-path> <Title: description>

If the input contains a colon, the part before becomes a bold title
and the part after becomes an indented description.
If no colon, the entire input becomes the bold title with no description.
Appends the entry followed by a trailing blank line.
Creates the file if it doesn't exist.
"""

import sys
from pathlib import Path

from task_lock import lock_backlog


def main():
    if len(sys.argv) < 3:
        print("Usage: task_add.py <file-path> <Title: description>", file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    text = " ".join(sys.argv[2:])

    if ":" in text:
        title, description = text.split(":", 1)
        title = title.strip()
        description = description.strip()
        entry = f"- [ ] **{title}**\n  {description}\n\n"
    else:
        entry = f"- [ ] **{text.strip()}**\n\n"

    with lock_backlog(file_path):
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(entry)

    print(f"Added: - [ ] **{title if ':' in text else text.strip()}**")


if __name__ == "__main__":
    main()
