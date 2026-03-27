"""Tests for task_unblock.py: unblocking [!] items."""

import subprocess
import sys
from pathlib import Path

SCRIPT = str(Path(__file__).resolve().parent.parent / 'task_unblock.py')


def run_unblock(file_path, name=None):
    """Run task_unblock.py and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, SCRIPT, str(file_path)]
    if name:
        cmd += ['--name', name]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=file_path.parent)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def test_unblock_first_blocked_item(tmp_path):
    f = tmp_path / 'plan.md'
    f.write_text(
        '- [x] **Step A**\n'
        '- [!] **Step B**\n'
        '  - blocked: deploy failed\n'
        '- [ ] **Step C**\n'
    )
    rc, stdout, _ = run_unblock(f)
    assert rc == 0
    assert '[ ] **Step B**' in stdout

    content = f.read_text()
    assert '- [ ] **Step B**\n' in content
    assert 'blocked:' not in content


def test_unblock_by_name(tmp_path):
    f = tmp_path / 'plan.md'
    f.write_text(
        '- [!] **Alpha**\n'
        '  - blocked: reason alpha\n'
        '- [!] **Beta**\n'
        '  - blocked: reason beta\n'
    )
    rc, stdout, _ = run_unblock(f, name='Beta')
    assert rc == 0
    assert '[ ] **Beta**' in stdout

    content = f.read_text()
    # Alpha still blocked.
    assert '- [!] **Alpha**\n' in content
    assert 'reason alpha' in content
    # Beta unblocked.
    assert '- [ ] **Beta**\n' in content
    assert 'reason beta' not in content


def test_unblock_no_blocked_items_exits_1(tmp_path):
    f = tmp_path / 'plan.md'
    f.write_text(
        '- [ ] **Step A**\n'
        '- [x] **Step B**\n'
    )
    rc, _, stderr = run_unblock(f)
    assert rc == 1
    assert 'No blocked items' in stderr


def test_unblock_removes_blocked_subbullet_preserves_others(tmp_path):
    f = tmp_path / 'plan.md'
    f.write_text(
        '- [!] **Task**\n'
        '  - plan: .llm/plans/some-plan.md\n'
        '  - blocked: the reason\n'
    )
    rc, _, _ = run_unblock(f)
    assert rc == 0

    content = f.read_text()
    assert '- [ ] **Task**\n' in content
    assert 'plan: .llm/plans/some-plan.md' in content
    assert 'blocked:' not in content


def test_backlog_requires_name(tmp_path):
    f = tmp_path / 'backlog.md'
    f.write_text('- [!] **Task A**\n  - blocked: reason\n')
    rc, _, stderr = run_unblock(f)
    assert rc == 1
    assert 'required' in stderr.lower()


def test_backlog_works_with_name(tmp_path):
    f = tmp_path / 'backlog.md'
    f.write_text('- [!] **Task A**\n  - blocked: reason\n')
    rc, stdout, _ = run_unblock(f, name='Task A')
    assert rc == 0
    assert 'Task A' in stdout
