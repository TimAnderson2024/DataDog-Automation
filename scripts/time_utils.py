from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import re

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

_UNIT_MS = {
    "s": 1000,
    "m": 60_000,
    "h": 3_600_000,
    "d": 86_400_000,
    "w": 604_800_000,
}

_NOW_RE = re.compile(r"^now(?:-(\d+)([smhdw]))?$")

def _to_unix_ms(t: str, now_ms: int) -> int:
    """
    Convert 'now' or 'now-<N><unit>' to unix ms.
    """
    m = _NOW_RE.match(t.strip())
    if not m:
        raise ValueError(f"Unsupported time format: {t!r} (expected 'now' or 'now-<N><unit>')")
    qty, unit = m.groups()
    if qty is None:
        return now_ms
    return now_ms - int(qty) * _UNIT_MS[unit]

def normalize_time(time_from: str, time_to: str) -> tuple[int, int]:
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    from_ms = _to_unix_ms(time_from, now_ms)
    to_ms = _to_unix_ms(time_to, now_ms)

    if from_ms > to_ms:
        raise ValueError(f"Invalid range: from ({time_from}) is after to ({time_to})")

    return (from_ms, to_ms)

def get_filtered_date_ranges(days_back: int):
    """
    Generate list of (from, to) date tuples for weekdays only in the last N weeks.
    Returns dates in ISO format suitable for DataDog API.
    """
    
    hours_ago = days_back * 24
    business, weekends = [], []
    while hours_ago > 0:
        time_from, time_to = f"now-{hours_ago}h", f"now-{hours_ago-24}h"
        if (datetime.now() - timedelta(hours_ago - 1)).weekday() < 5:
            business.append((time_from, time_to))
        else:
            weekends.append((time_from, time_to))
        hours_ago -= 24

    return business, weekends