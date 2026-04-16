"""Top-level shim — delegates to millpy.entrypoints.open_vscode."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from millpy.entrypoints.open_vscode import main
sys.exit(main())
