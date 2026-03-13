import re

CHECKBOX_RE = re.compile(r'^(\s*)- \[(.)\] ')

def change_state(line, new_state):
    """Replace the state character in a checkbox line."""
    if not CHECKBOX_RE.match(line):
        raise ValueError(f'Line does not match checkbox pattern: {line!r}')
    return re.sub(r'^(\s*- \[)[> p1-9!xp](])', lambda m: f'{m.group(1)}{new_state}{m.group(2)}', line)

def is_incomplete(state):
    """Return True if state represents an actionable (incomplete) item."""
    return state in (' ', '>', 'p') or state.isdigit()
