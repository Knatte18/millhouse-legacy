#!/usr/bin/env python3
"""Add or update a sub-bullet on a checkbox item."""

import sys

from lib.locking import locked
from lib.parsing import read_lines, find_task, find_item_by_index
from lib.subbullet import upsert_subbullet
from lib.io import write_file, is_backlog


def main():
    if len(sys.argv) < 4:
        print('Usage: task_subbullet.py <file-path> <identifier> "<key>: <value>"',
              file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]
    identifier = sys.argv[2]
    kv_string = sys.argv[3]

    colon_pos = kv_string.find(':')
    if colon_pos == -1:
        print('Value must be in "key: value" format.', file=sys.stderr)
        sys.exit(1)

    key = kv_string[:colon_pos].strip()
    value = kv_string[colon_pos + 1:].strip()

    with locked(file_path):
        lines = read_lines(file_path)

        if identifier.isdigit():
            idx = find_item_by_index(lines, int(identifier))
        else:
            idx = find_task(lines, name=identifier, top_level_only=False)

        if idx is None:
            print(f'Item not found: {identifier}', file=sys.stderr)
            sys.exit(1)

        result = upsert_subbullet(lines, idx, key, value)
        write_file(file_path, lines, normalize=is_backlog(file_path))
        print(result.rstrip('\n'))


if __name__ == '__main__':
    main()
