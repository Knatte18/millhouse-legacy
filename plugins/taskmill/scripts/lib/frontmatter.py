def find_frontmatter(lines):
    """Find YAML frontmatter delimiters. Returns (start, end) or None."""
    if not lines or lines[0].rstrip('\n') != '---':
        return None
    for i in range(1, len(lines)):
        if lines[i].rstrip('\n') == '---':
            return (0, i)
    return None

def upsert_frontmatter_key(lines, key, value):
    """Insert or update a key in YAML frontmatter. Returns the formatted line."""
    bounds = find_frontmatter(lines)
    if bounds is None:
        raise ValueError('No YAML frontmatter found.')
    start, end = bounds
    formatted_line = f'{key}: {value}\n'

    for i in range(start + 1, end):
        if lines[i].startswith(f'{key}:'):
            lines[i] = formatted_line
            return formatted_line

    lines.insert(end, formatted_line)
    return formatted_line
