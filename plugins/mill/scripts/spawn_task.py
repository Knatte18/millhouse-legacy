"""Top-level shim — delegates to millpy.entrypoints.spawn_task."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from millpy.entrypoints.spawn_task import main
sys.exit(main())
