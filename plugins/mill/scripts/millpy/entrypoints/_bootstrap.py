"""
_bootstrap.py — sys.path injector for millpy entrypoints.

Import this module first in every entrypoint before any `import millpy.*`.
The import has the side effect of inserting the `plugins/mill/scripts/` directory
onto sys.path so that `import millpy.*` resolves correctly regardless of the
working directory or invocation method (python -m, direct file execution, shim).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
