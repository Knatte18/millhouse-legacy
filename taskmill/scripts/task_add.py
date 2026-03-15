#!/usr/bin/env python3
"""Append a new checkbox item to a file."""

import sys
from pathlib import Path

from lib.locking import locked
from lib.io import write_file, is_backlog


def main():
    if len(sys.argv) < 3:
        print('Usage: task_add.py <file-path> <Title: description>', file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    text = ' '.join(sys.argv[2:])

    if ':' in text:
        title, description = text.split(':', 1)
        entry = f'- [ ] **{title.strip()}**\n  {description.strip()}\n\n'
    else:
        entry = f'- [ ] **{text.strip()}**\n\n'

    with locked(file_path):
        p = Path(file_path)
        if p.exists():
            content = p.read_text(encoding='utf-8')
            if not content.endswith('\n'):
                content += '\n'
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            content = ''
        content += entry

        # Write via lines for write_file compatibility
        lines = content.splitlines(keepends=True)
        if not content.endswith('\n'):
            lines.append('\n')
        write_file(file_path, lines, normalize=is_backlog(file_path))
        print(entry.strip())


if __name__ == '__main__':
    main()
