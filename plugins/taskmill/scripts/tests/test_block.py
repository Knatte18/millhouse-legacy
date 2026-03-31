"""Tests for task_block.py: blocking items."""

import subprocess
import sys
from pathlib import Path

SCRIPT = str(Path(__file__).resolve().parent.parent / 'task_block.py')


def run_block(file_path, reason=None, name=None):
    """Run task_block.py and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, SCRIPT, str(file_path)]
    if reason:
        cmd.append(reason)
    if name:
        cmd += ['--name', name]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=file_path.parent)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def test_backlog_requires_name(tmp_path):
    f = tmp_path / 'backlog.md'
    f.write_text('- [ ] **Task A**\n- [ ] **Task B**\n')
    rc, _, stderr = run_block(f, reason='some reason')
    assert rc == 1
    assert 'required' in stderr.lower()
    # File unchanged.
    assert f.read_text() == '- [ ] **Task A**\n- [ ] **Task B**\n'


def test_backlog_works_with_name(tmp_path):
    f = tmp_path / 'backlog.md'
    f.write_text('- [ ] **Task A**\n- [ ] **Task B**\n')
    rc, stdout, _ = run_block(f, reason='broken', name='Task B')
    assert rc == 0
    assert 'Task B' in stdout
    content = f.read_text()
    assert '- [!] **Task B**' in content
    assert '- [ ] **Task A**' in content


def test_non_backlog_works_without_name(tmp_path):
    f = tmp_path / 'plan.md'
    f.write_text('- [ ] **Step A**\n- [ ] **Step B**\n')
    rc, stdout, _ = run_block(f, reason='failed')
    assert rc == 0
    assert 'Step A' in stdout
    content = f.read_text()
    assert '- [!] **Step A**' in content
