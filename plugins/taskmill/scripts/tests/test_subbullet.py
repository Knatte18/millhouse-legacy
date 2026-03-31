"""Tests for lib.subbullet: upsert and remove operations."""

from lib.subbullet import upsert_subbullet, remove_subbullet


def test_upsert_adds_new_subbullet():
    lines = [
        '- [ ] **Task A**\n',
        '\n',
    ]
    result = upsert_subbullet(lines, 0, 'blocked', 'waiting on deploy')
    assert result == '  - blocked: waiting on deploy\n'
    assert lines == [
        '- [ ] **Task A**\n',
        '  - blocked: waiting on deploy\n',
        '\n',
    ]


def test_upsert_updates_existing_subbullet():
    lines = [
        '- [!] **Task A**\n',
        '  - blocked: old reason\n',
        '\n',
    ]
    upsert_subbullet(lines, 0, 'blocked', 'new reason')
    assert lines == [
        '- [!] **Task A**\n',
        '  - blocked: new reason\n',
        '\n',
    ]


def test_upsert_preserves_other_subbullets():
    lines = [
        '- [p] **Task A**\n',
        '  - plan: .llm/plans/some-plan.md\n',
        '\n',
    ]
    upsert_subbullet(lines, 0, 'blocked', 'reason')
    assert lines == [
        '- [p] **Task A**\n',
        '  - plan: .llm/plans/some-plan.md\n',
        '  - blocked: reason\n',
        '\n',
    ]


def test_remove_subbullet_removes_existing():
    lines = [
        '- [!] **Task A**\n',
        '  - blocked: some reason\n',
        '\n',
    ]
    removed = remove_subbullet(lines, 0, 'blocked')
    assert removed is True
    assert lines == [
        '- [!] **Task A**\n',
        '\n',
    ]


def test_remove_subbullet_noop_when_missing():
    lines = [
        '- [ ] **Task A**\n',
        '  - plan: .llm/plans/some-plan.md\n',
        '\n',
    ]
    removed = remove_subbullet(lines, 0, 'blocked')
    assert removed is False
    assert lines == [
        '- [ ] **Task A**\n',
        '  - plan: .llm/plans/some-plan.md\n',
        '\n',
    ]


def test_remove_subbullet_preserves_other_subbullets():
    lines = [
        '- [!] **Task A**\n',
        '  - plan: .llm/plans/some-plan.md\n',
        '  - blocked: reason\n',
        '\n',
    ]
    removed = remove_subbullet(lines, 0, 'blocked')
    assert removed is True
    assert lines == [
        '- [!] **Task A**\n',
        '  - plan: .llm/plans/some-plan.md\n',
        '\n',
    ]
