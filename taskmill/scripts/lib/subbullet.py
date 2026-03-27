"""Sub-bullet manipulation for checkbox items."""

import re


def upsert_subbullet(lines, idx, key, value):
    """Add or update a sub-bullet on the item at idx. Returns the sub-bullet line."""
    key_pattern = re.compile(rf'^\s*-\s+{re.escape(key)}:')
    subbullet_line = f'  - {key}: {value}\n'

    sub_start = idx + 1
    sub_end = sub_start
    existing_idx = None

    while sub_end < len(lines):
        line = lines[sub_end]
        if line.strip() == '' or (not line.startswith('  ') and not line.startswith('\t')):
            break
        if key_pattern.match(line):
            existing_idx = sub_end
        sub_end += 1

    if existing_idx is not None:
        lines[existing_idx] = subbullet_line
    else:
        lines.insert(sub_end, subbullet_line)

    return subbullet_line


def remove_subbullet(lines, idx, key):
    """Remove a sub-bullet matching `key:` from the item at idx. Returns True if a line was removed."""
    key_pattern = re.compile(rf'^\s*-\s+{re.escape(key)}:')

    sub_start = idx + 1
    while sub_start < len(lines):
        line = lines[sub_start]
        if line.strip() == '' or (not line.startswith('  ') and not line.startswith('\t')):
            break
        if key_pattern.match(line):
            del lines[sub_start]
            return True
        sub_start += 1

    return False
