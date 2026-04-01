#!/bin/bash
# Link all millhouse plugins to source, bypassing the plugin cache.
# Uses Windows junctions (no admin required) or Unix symlinks.
# Run from the millhouse repo root.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR/plugins"
CACHE_DIR=~/.claude/plugins/cache/millhouse

if [ ! -d "$CACHE_DIR" ]; then
  echo "Error: Plugin cache not found at $CACHE_DIR"
  echo "Run 'claude plugin marketplace add' and install plugins first (see INSTALL.md step 1)."
  exit 1
fi

is_windows() {
  [[ "$OSTYPE" == "msys"* || "$OSTYPE" == "mingw"* || "$OSTYPE" == "cygwin"* ]]
}

# Convert /c/path/to/dir to C:\path\to\dir
to_win_path() {
  local p="$1"
  # Remove trailing slash
  p="${p%/}"
  # Convert drive letter
  if [[ "$p" =~ ^/([a-zA-Z])/ ]]; then
    p="${BASH_REMATCH[1]^^}:${p:2}"
  fi
  # Convert slashes
  echo "${p//\//\\}"
}

for plugin in "$SOURCE_DIR"/*/; do
  name=$(basename "$plugin")
  target="$CACHE_DIR/$name/1.0.0"

  if [ ! -d "$CACHE_DIR/$name" ]; then
    echo "Skipped (not installed): $name"
    continue
  fi

  # Check if already a junction (Windows) or symlink (Unix)
  if is_windows; then
    win_target=$(to_win_path "$target")
    if cmd.exe //c "fsutil reparsepoint query $win_target" > /dev/null 2>&1; then
      echo "Already linked: $name"
      continue
    fi
  elif [ -L "$target" ]; then
    echo "Already linked: $name"
    continue
  fi

  # Backup existing cache
  if [ -d "$target" ]; then
    rm -rf "${target}.bak"
    mv "$target" "${target}.bak"
  fi

  # Create link
  if is_windows; then
    win_target=$(to_win_path "$target")
    win_source=$(to_win_path "$plugin")
    cmd.exe //c "mklink /J $win_target $win_source" > /dev/null 2>&1
  else
    ln -s "$plugin" "$target"
  fi

  echo "Linked: $name"
done

echo ""
echo "Done. Plugin edits are now live immediately."
