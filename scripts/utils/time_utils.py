from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

def iso_to_unix_milliseconds(iso_time: str) -> int:
    """
    Convert an ISO 8601 formatted time string to Unix timestamp in milliseconds.
    """
    dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1000)

def iso_to_unix_seconds(iso_time: str) -> int:
    """
    Convert an ISO 8601 formatted time string to Unix timestamp in seconds.
    """
    return iso_to_unix_milliseconds(iso_time) // 1000

def time_range_iso_hours_ago(hours_ago: int) -> str:
    """
    Get the ISO 8601 formatted time string for a time 'hours_ago' hours before now.
    """
    time_to = datetime.now()
    time_from = time_to - timedelta(hours=hours_ago)
    return time_from.isoformat(), time_to.isoformat()

def unix_to_iso(unix_time: int | float) -> str:
    unix_time = float(unix_time)

    # Heuristic: anything above ~1e12 is almost certainly ms since epoch
    if unix_time > 1_000_000_000_000:
        unix_time /= 1000.0

    dt = datetime.fromtimestamp(unix_time, tz=ZoneInfo("America/New_York"))
    return dt.strftime("%b %#d, %Y at %#I:%M %p est")