#!/usr/bin/env python3
"""Print current UTC time as YYYY-MM-DD-HHMMSS."""

from datetime import datetime, timezone

print(datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S'))
