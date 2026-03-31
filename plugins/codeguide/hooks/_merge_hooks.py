"""
Merge composable hook JSON files into a single hooks.json.

Usage:
    python _merge_hooks.py <output_path> <input_path> [<input_path> ...]

Each input file has the structure {"hooks": {"EventName": [...]}}. The merge
concatenates arrays for each event key across all inputs.
"""

import json
import sys


def merge(files: list[str]) -> dict:
    merged: dict[str, list] = {}
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for event, entries in data.get("hooks", {}).items():
            merged.setdefault(event, []).extend(entries)
    return {"hooks": merged}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <output> <input> [<input> ...]", file=sys.stderr)
        sys.exit(1)

    output_path = sys.argv[1]
    input_paths = sys.argv[2:]
    result = merge(input_paths)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")
