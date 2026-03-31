from datetime import datetime, timezone


def utcnow():
    """Return current UTC time as YYYY-MM-DD-HHMMSS string."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S')
