#!/usr/bin/env python
"""spawn-agent.py — hyphenated shim forwarding to millpy.entrypoints.spawn_agent.main."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from millpy.entrypoints.spawn_agent import main
sys.exit(main(sys.argv[1:]))
