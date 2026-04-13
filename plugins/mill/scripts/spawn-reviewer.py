#!/usr/bin/env python3
"""
spawn-reviewer — CLI entry point.

This file exists so the script can be invoked as:
  python plugins/mill/scripts/spawn-reviewer.py --phase code --round 1 ...

The actual implementation lives in spawn_reviewer.py (importable module).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spawn_reviewer import main  # noqa: E402

if __name__ == '__main__':
    main()
