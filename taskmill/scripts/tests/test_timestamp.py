import re
from unittest.mock import patch
from datetime import datetime, timezone

from lib.timestamp import utcnow


PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}-\d{6}$')


def test_utcnow_format():
    result = utcnow()
    assert PATTERN.match(result), f'Expected YYYY-MM-DD-HHMMSS, got {result}'


def test_utcnow_uses_utc():
    fixed = datetime(2026, 1, 15, 8, 30, 45, tzinfo=timezone.utc)
    with patch('lib.timestamp.datetime') as mock_dt:
        mock_dt.now.return_value = fixed
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        assert utcnow() == '2026-01-15-083045'
        mock_dt.now.assert_called_once_with(timezone.utc)
