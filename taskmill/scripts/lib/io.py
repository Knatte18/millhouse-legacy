from pathlib import Path
from .backlog_format import normalize_backlog

def is_backlog(path):
    """Return True if the path is a backlog.md file."""
    return Path(path).name == 'backlog.md'

def write_file(path, lines, normalize=False):
    """Join lines, optionally normalize, and write to path."""
    content = ''.join(lines)
    if normalize:
        content = normalize_backlog(content)
    Path(path).write_text(content, encoding='utf-8')
