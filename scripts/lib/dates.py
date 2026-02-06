"""Date utilities for last2hours skill."""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Union


def parse_range(range_str: str) -> timedelta:
    """Parse a natural language time range string into a timedelta.

    Supports formats like:
        "2 hours", "2hours", "2h"
        "3 days", "3days", "3d"
        "2 weeks", "2weeks", "2w"
        "6 months", "6months", "6mo"

    Args:
        range_str: Natural language time range (e.g., "2 hours", "3 days")

    Returns:
        timedelta representing the duration

    Raises:
        ValueError: If the format is not recognized
    """
    range_str = range_str.strip().lower()

    # Match patterns like "2 hours", "2hours", "2h"
    match = re.match(r'^(\d+)\s*(h|hours?|d|days?|w|weeks?|mo|months?)$', range_str)
    if not match:
        raise ValueError(f"Invalid range format: '{range_str}'. Use formats like '2 hours', '3 days', '2 weeks', '6 months'")

    amount = int(match.group(1))
    unit = match.group(2)

    if unit in ('h', 'hour', 'hours'):
        return timedelta(hours=amount)
    elif unit in ('d', 'day', 'days'):
        return timedelta(days=amount)
    elif unit in ('w', 'week', 'weeks'):
        return timedelta(weeks=amount)
    elif unit in ('mo', 'month', 'months'):
        # Approximate months as 30 days
        return timedelta(days=amount * 30)
    else:
        raise ValueError(f"Unknown time unit: '{unit}'")


def get_date_range(duration: Union[int, timedelta] = timedelta(hours=2)) -> Tuple[str, str]:
    """Get the date range for a given duration.

    Args:
        duration: Either an int (days, for backwards compatibility) or a timedelta

    Returns:
        Tuple of (from_date, to_date) as ISO 8601 strings.
        For durations < 1 day, returns full datetime strings.
        For durations >= 1 day, returns YYYY-MM-DD date strings.
    """
    # Backwards compatibility: if int passed, treat as days
    if isinstance(duration, int):
        duration = timedelta(days=duration)

    now = datetime.now(timezone.utc)
    from_dt = now - duration

    # For short durations (< 1 day), use full datetime precision
    if duration < timedelta(days=1):
        return from_dt.isoformat(), now.isoformat()
    else:
        # For longer durations, use date-only format (existing behavior)
        return from_dt.date().isoformat(), now.date().isoformat()


def get_range_label(duration: timedelta) -> str:
    """Get a human-readable label for a time range.

    Args:
        duration: The timedelta to describe

    Returns:
        String like "last 2 hours", "last 3 days", etc.
    """
    total_seconds = duration.total_seconds()
    total_hours = total_seconds / 3600
    total_days = total_seconds / 86400

    if total_hours < 24:
        hours = int(total_hours)
        return f"last {hours} hour{'s' if hours != 1 else ''}"
    elif total_days < 7:
        days = int(total_days)
        return f"last {days} day{'s' if days != 1 else ''}"
    elif total_days < 30:
        weeks = int(total_days / 7)
        return f"last {weeks} week{'s' if weeks != 1 else ''}"
    else:
        months = int(total_days / 30)
        return f"last {months} month{'s' if months != 1 else ''}"


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse a date string in various formats.

    Supports: YYYY-MM-DD, ISO 8601, Unix timestamp
    """
    if not date_str:
        return None

    # Try Unix timestamp (from Reddit)
    try:
        ts = float(date_str)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, TypeError):
        pass

    # Try ISO formats
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def timestamp_to_date(ts: Optional[float]) -> Optional[str]:
    """Convert Unix timestamp to YYYY-MM-DD string."""
    if ts is None:
        return None
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.date().isoformat()
    except (ValueError, TypeError, OSError):
        return None


def get_date_confidence(date_str: Optional[str], from_date: str, to_date: str) -> str:
    """Determine confidence level for a date.

    Args:
        date_str: The date to check (YYYY-MM-DD or None)
        from_date: Start of valid range (YYYY-MM-DD)
        to_date: End of valid range (YYYY-MM-DD)

    Returns:
        'high', 'med', or 'low'
    """
    if not date_str:
        return 'low'

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        start = datetime.strptime(from_date, "%Y-%m-%d").date()
        end = datetime.strptime(to_date, "%Y-%m-%d").date()

        if start <= dt <= end:
            return 'high'
        elif dt < start:
            # Older than range
            return 'low'
        else:
            # Future date (suspicious)
            return 'low'
    except ValueError:
        return 'low'


def days_ago(date_str: Optional[str]) -> Optional[int]:
    """Calculate how many days ago a date is.

    Returns None if date is invalid or missing.
    """
    if not date_str:
        return None

    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.now(timezone.utc).date()
        delta = today - dt
        return delta.days
    except ValueError:
        return None


def recency_score(date_str: Optional[str], max_duration: Union[int, timedelta] = 30) -> int:
    """Calculate recency score (0-100).

    Args:
        date_str: Date string (YYYY-MM-DD or ISO 8601 datetime)
        max_duration: Either an int (days, for backwards compatibility) or a timedelta

    Returns:
        Score from 0-100 where 100 = now and 0 = at or beyond max_duration
    """
    if not date_str:
        return 0  # Unknown date gets worst score

    # Parse the date
    parsed = parse_date(date_str)
    if parsed is None:
        return 0

    now = datetime.now(timezone.utc)
    age = now - parsed

    # Handle backwards compatibility
    if isinstance(max_duration, int):
        max_duration = timedelta(days=max_duration)

    # Calculate score
    if age.total_seconds() < 0:
        return 100  # Future date (treat as now)
    if age >= max_duration:
        return 0

    # Linear interpolation: 100 at age=0, 0 at age=max_duration
    ratio = age.total_seconds() / max_duration.total_seconds()
    return int(100 * (1 - ratio))
