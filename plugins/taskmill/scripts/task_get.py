#!/usr/bin/env python3
"""Extract the next incomplete task/step with its context lines."""

import argparse
import sys

from lib.locking import locked
from lib.parsing import read_lines, find_task, extract_block


def main():
    parser = argparse.ArgumentParser(description='Get next incomplete task')
    parser.add_argument('file', help='Path to the task file')
    parser.add_argument('--include-planned', action='store_true',
                        help='Include [p] tasks in selection priority')
    args = parser.parse_args()

    states = ['>', 'p', ' '] if args.include_planned else ['>', ' ']

    with locked(args.file):
        lines = read_lines(args.file)
        idx = find_task(lines, states=states)
        if idx is None:
            print('No incomplete items found.', file=sys.stderr)
            sys.exit(1)
        block = extract_block(lines, idx)
        print(''.join(block), end='')


if __name__ == '__main__':
    main()
