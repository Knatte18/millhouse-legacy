"""Top-level shim — delegates to millpy.entrypoints.worktree."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from millpy.entrypoints.worktree import main
sys.exit(main())
