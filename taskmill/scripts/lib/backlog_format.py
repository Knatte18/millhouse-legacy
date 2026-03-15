import re

HEADER = '# Backlog'
_CHECKBOX_RE = re.compile(r'^- \[.\] ')

def normalize_backlog(text):
    """Normalize backlog formatting: header, blank lines between entries, trailing newline."""
    lines = text.splitlines()

    # Strip leading blank lines
    while lines and lines[0].strip() == '':
        lines.pop(0)

    # Ensure header
    if lines and lines[0].startswith('# '):
        lines[0] = HEADER
    else:
        lines.insert(0, HEADER)

    # Ensure blank line after header
    if len(lines) < 2 or lines[1].strip() != '':
        lines.insert(1, '')

    # Ensure blank line before each top-level checkbox
    expanded = []
    for i, line in enumerate(lines):
        if _CHECKBOX_RE.match(line) and i > 0 and expanded and expanded[-1].strip() != '':
            expanded.append('')
        expanded.append(line)

    # Collapse consecutive blank lines
    normalized = []
    previous_blank = False
    for line in expanded:
        is_blank = line.strip() == ''
        if is_blank and previous_blank:
            continue
        normalized.append(line)
        previous_blank = is_blank

    # Remove trailing blank lines
    while normalized and normalized[-1].strip() == '':
        normalized.pop()

    return '\n'.join(normalized) + '\n'
