"""Shared fixtures for script tests."""

import sys
from pathlib import Path

# Add scripts dir to path so `lib` imports work.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
