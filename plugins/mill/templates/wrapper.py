"""Forwarding wrapper — delegates to <ENTRYPOINT> in the mill plugin cache."""
import re, sys, pathlib

_cache = pathlib.Path.home() / ".claude" / "plugins" / "cache" / "millhouse" / "mill"
_semver = re.compile(r"^\d+\.\d+\.\d+$")
_versions = sorted(
    [d.name for d in _cache.iterdir() if d.is_dir() and _semver.match(d.name)],
    reverse=True,
)
if not _versions:
    print("ERROR: mill plugin not found at", _cache, file=sys.stderr)
    sys.exit(1)
sys.path.insert(0, str(_cache / _versions[0] / "scripts"))

from millpy.entrypoints.<ENTRYPOINT> import main

sys.exit(main())
