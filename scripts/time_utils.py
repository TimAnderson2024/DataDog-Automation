from datetime import datetime, timedelta, timezone
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

def _second_sunday_of_march(year: int) -> datetime:
    d = datetime(year, 3, 1)
    # weekday(): Mon=0 .. Sun=6 -> find first Sunday, then add 7 days
    first_sunday = 1 + ((6 - d.weekday()) % 7)
    second_sunday = first_sunday + 7
    return datetime(year, 3, second_sunday, 2, 0, 0)

def _first_sunday_of_november(year: int) -> datetime:
    d = datetime(year, 11, 1)
    first_sunday = 1 + ((6 - d.weekday()) % 7)
    return datetime(year, 11, first_sunday, 2, 0, 0)

def _is_eastern_dst(utc_dt: datetime) -> bool:
    # utc_dt must be timezone-naive UTC (or use utc_dt.replace(tzinfo=timezone.utc))
    year = utc_dt.year
    # transitions are defined in local wall time (Eastern). We'll compute their UTC instants.
    # Standard offset = -5, DST offset = -4
    std_offset = timedelta(hours=-5)
    dst_offset = timedelta(hours=-4)

    # local transition datetimes (wall clock) at 02:00 local
    start_local = _second_sunday_of_march(year)  # 02:00 local standard -> becomes 03:00 local DST
    end_local = _first_sunday_of_november(year)  # 02:00 local DST -> becomes 01:00 local standard

    # Convert those local times to UTC instants:
    # - start_local happens while standard time was in effect (before spring forward): UTC = local - std_offset
    start_utc = (start_local - std_offset)
    # - end_local happens while DST was in effect: UTC = local - dst_offset
    end_utc = (end_local - dst_offset)

    # If DST window crosses year boundary (it doesn't for US rules), handle normally
    return start_utc <= utc_dt < end_utc

def unix_to_iso(unix_time: int | float) -> str:
    unix_time = float(unix_time)
    if unix_time > 1_000_000_000_000:
        unix_time /= 1000.0

    # get UTC datetime (naive) for decision making
    utc_dt = datetime.utcfromtimestamp(unix_time)

    if _is_eastern_dst(utc_dt):
        offset = timedelta(hours=-4)
        label = "edt"
    else:
        offset = timedelta(hours=-5)
        label = "est"

    # create aware datetime using computed offset and format without platform-specific flags
    tz = timezone(offset)
    dt = datetime.fromtimestamp(unix_time, tz=tz)

    # Build a portable formatted string (avoid %-d / %#d portability issues)
    month = dt.strftime("%b")
    day = dt.day
    year = dt.year
    hour = dt.strftime("%I").lstrip("0") or "0"
    minute = dt.strftime("%M")
    ampm = dt.strftime("%p")
    return f"{month} {day}, {year} at {hour}:{minute} {ampm} {label}"

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