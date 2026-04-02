#!/usr/bin/env python3
"""Print current UTC time in the requested format.

Usage:
    python utcnow.py              # slug:  2026-04-02-130419
    python utcnow.py --iso        # ISO:   2026-04-02T13:04:19.000Z
"""

import sys
from datetime import datetime, timezone

now = datetime.now(timezone.utc)

if "--iso" in sys.argv:
    print(now.strftime("%Y-%m-%dT%H:%M:%S.000Z"))
else:
    print(now.strftime("%Y-%m-%d-%H%M%S"))
