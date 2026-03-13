#!/usr/bin/env python3
"""Set the finished: timestamp in a plan file's YAML frontmatter."""

import sys
from datetime import datetime, timezone

from lib.parsing import read_lines
from lib.frontmatter import upsert_frontmatter_key
from lib.io import write_file


def main():
    if len(sys.argv) < 2:
        print('Usage: plan_finish.py <plan-file>', file=sys.stderr)
        sys.exit(1)

    file_path = sys.argv[1]

    try:
        lines = read_lines(file_path)
    except FileNotFoundError:
        print(f'File not found: {file_path}', file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    try:
        finished_line = upsert_frontmatter_key(lines, 'finished', now)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    write_file(file_path, lines)
    print(finished_line.rstrip('\n'))


if __name__ == '__main__':
    main()
