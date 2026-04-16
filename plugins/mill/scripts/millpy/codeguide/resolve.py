"""
Path resolution for codeguide hooks.

Two-tier resolution:
- Routing files (Overview.md, modules/) resolve from cwd — each folder with
  a _codeguide/ is a self-contained routing node.
- Metadata files (config.yaml, local-rules.md, DocumentationGuide.md,
  NavigationHooks.md) resolve by walking up from cwd to the nearest ancestor
  that contains them. These are repo-level concerns.
"""

import os
import pathlib

# Metadata file that anchors the walk-up search. Change here if renamed.
METADATA_ANCHOR = "config.yaml"


def routing_root(cwd: str | None = None) -> pathlib.Path:
    """Return the cwd-level _codeguide/ directory (routing context)."""
    return pathlib.Path(cwd or os.getcwd()) / "_codeguide"


def find_metadata(filename: str, cwd: str | None = None) -> pathlib.Path | None:
    """Walk up from cwd to find _codeguide/<filename>. Stops at git root."""
    current = pathlib.Path(cwd or os.getcwd()).resolve()
    while True:
        candidate = current / "_codeguide" / filename
        if candidate.exists():
            return candidate
        if (current / ".git").exists():
            return None
        parent = current.parent
        if parent == current:
            return None
        current = parent


def config_path(cwd: str | None = None) -> pathlib.Path | None:
    """Find the nearest metadata anchor (config.yaml by default)."""
    return find_metadata(METADATA_ANCHOR, cwd)


def load_config_flag(flag: str, cwd: str | None = None) -> bool:
    """Read a boolean flag from the nearest config.yaml. Returns False if not found."""
    path = config_path(cwd)
    if path is None:
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{flag}:"):
                    value = line.split(":", 1)[1].strip().lower()
                    return value == "true"
    except FileNotFoundError:
        pass
    return False


def metadata_root(cwd: str | None = None) -> pathlib.Path | None:
    """Find the nearest _codeguide/ containing the metadata anchor."""
    path = config_path(cwd)
    return path.parent if path else None


def load_source_extensions(cwd: str | None = None) -> list[str]:
    """Load source extensions from the nearest config.yaml."""
    path = config_path(cwd)
    if path is None:
        return []
    extensions = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("- ."):
                    extensions.append(line[2:].strip())
    except FileNotFoundError:
        pass
    return extensions


if __name__ == "__main__":
    root = metadata_root()
    if root:
        print(root)
    else:
        print("ERROR: no _codeguide/ with config.yaml found", file=__import__("sys").stderr)
        __import__("sys").exit(1)
