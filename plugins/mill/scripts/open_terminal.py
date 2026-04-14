#!/usr/bin/env python
"""Forwarding shim. Canonical implementation: millpy.entrypoints.open_terminal."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from millpy.entrypoints.open_terminal import main

sys.exit(main(sys.argv[1:]))
