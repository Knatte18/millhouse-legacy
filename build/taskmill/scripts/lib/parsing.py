from pathlib import Path
from .state import CHECKBOX_RE, is_incomplete

def read_lines(path):
    """Read a file and return splitlines(keepends=True)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f'File not found: {path}')
    return p.read_text(encoding='utf-8').splitlines(keepends=True)

def find_task(lines, name=None, states=None, top_level_only=True, skip_claimed=False):
    """Find a task by name or by state priority. Returns line index or None."""
    if name is not None:
        name_lower = name.lower()
        for i, line in enumerate(lines):
            m = CHECKBOX_RE.match(line)
            if not m:
                continue
            indent, state = m.group(1), m.group(2)
            if top_level_only and len(indent) > 0:
                continue
            if skip_claimed and state.isdigit():
                continue  # skip already-claimed tasks
            if name_lower in line.lower():
                return i
        return None

    if states is None:
        return None

    for target_state in states:
        for i, line in enumerate(lines):
            m = CHECKBOX_RE.match(line)
            if not m:
                continue
            indent, state = m.group(1), m.group(2)
            if top_level_only and len(indent) > 0:
                continue
            if state.isdigit():
                continue  # skip claimed tasks in state-priority search
            if state == target_state:
                return i
    return None

def find_incomplete(lines):
    """Find the first incomplete item at any indent level. Returns index or None."""
    for i, line in enumerate(lines):
        m = CHECKBOX_RE.match(line)
        if m and is_incomplete(m.group(2)):
            return i
    return None

def find_item_by_index(lines, index):
    """Find the Nth checkbox item (1-based). Returns line index or None."""
    count = 0
    for i, line in enumerate(lines):
        if CHECKBOX_RE.match(line):
            count += 1
            if count == index:
                return i
    return None

def extract_block(lines, start):
    """Return the task line plus all contiguous indented sub-bullets."""
    result = [lines[start]]
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.strip() == '':
            continue
        if line.startswith('  ') or line.startswith('\t'):
            result.append(line)
        else:
            break
    return result

def delete_block(lines, start):
    """Remove task line, indented sub-bullets, and one trailing blank line."""
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() == '':
            end += 1
            break
        if line.startswith('  ') or line.startswith('\t'):
            end += 1
        else:
            break
    return lines[:start] + lines[end:]

def find_used_digits(lines):
    """Find all digit states currently in use."""
    used = set()
    for line in lines:
        m = CHECKBOX_RE.match(line)
        if m and m.group(2).isdigit():
            used.add(int(m.group(2)))
    return used

def find_lowest_unused_digit(used):
    """Find the lowest unused digit 1-9."""
    for n in range(1, 10):
        if n not in used:
            return n
    return None
