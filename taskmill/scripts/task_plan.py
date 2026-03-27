#!/usr/bin/env python3
"""Mark a task as planned and link its plan file."""

import argparse
import sys

from lib.state import change_state
from lib.locking import locked
from lib.parsing import read_lines, find_task
from lib.subbullet import upsert_subbullet
from lib.io import write_file, is_backlog


def main():
    parser = argparse.ArgumentParser(description='Mark a task as planned with a plan file link')
    parser.add_argument('--state', default='p',
                        help="State character to set (default: 'p'). Use ' ' for parking.")
    parser.add_argument('file', help='Path to the backlog file')
    parser.add_argument('task_name', help='Task name (case-insensitive substring match)')
    parser.add_argument('plan_path', help='Path to the plan file')
    args = parser.parse_args()

    if len(args.state) != 1:
        print(f'--state must be a single character, got: {args.state!r}', file=sys.stderr)
        sys.exit(1)

    with locked(args.file):
        lines = read_lines(args.file)

        idx = find_task(lines, name=args.task_name)
        if idx is None:
            print(f'Task not found: {args.task_name}', file=sys.stderr)
            sys.exit(1)

        lines[idx] = change_state(lines[idx], args.state)
        upsert_subbullet(lines, idx, 'plan', args.plan_path)

        write_file(args.file, lines, normalize=is_backlog(args.file))
        print(lines[idx].rstrip('\n'))


if __name__ == '__main__':
    main()
