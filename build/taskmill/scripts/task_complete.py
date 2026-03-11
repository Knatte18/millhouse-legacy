#!/usr/bin/env python3
"""Mark the first incomplete item as done, or delete it."""

import argparse
import sys

from lib.state import change_state
from lib.locking import locked
from lib.parsing import read_lines, find_incomplete, delete_block
from lib.io import write_file, is_backlog


def main():
    parser = argparse.ArgumentParser(description='Complete the first incomplete task')
    parser.add_argument('file', help='Path to the task file')
    parser.add_argument('--delete', action='store_true',
                        help='Delete the entry instead of marking [x]')
    args = parser.parse_args()

    with locked(args.file):
        lines = read_lines(args.file)
        idx = find_incomplete(lines)
        if idx is None:
            print('No incomplete items found.', file=sys.stderr)
            sys.exit(1)

        completed_line = lines[idx].rstrip('\n')
        print(completed_line)

        if args.delete:
            lines = delete_block(lines, idx)
        else:
            lines[idx] = change_state(lines[idx], 'x')

        write_file(args.file, lines, normalize=is_backlog(args.file))


if __name__ == '__main__':
    main()
