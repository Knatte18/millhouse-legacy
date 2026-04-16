"""Top-level shim — delegates to millpy.entrypoints.fetch_issues."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from millpy.entrypoints.fetch_issues import main
sys.exit(main())
