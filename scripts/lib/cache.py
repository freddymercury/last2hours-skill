"""Caching utilities for last2hours skill."""

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, Union

CACHE_DIR = Path.home() / ".cache" / "last2hours"
DEFAULT_TTL_HOURS = 24
MODEL_CACHE_TTL_DAYS = 7

# Minimum TTL to avoid excessive API calls
MIN_TTL_MINUTES = 15


def calculate_ttl(duration: Union[int, timedelta]) -> float:
    """Calculate appropriate cache TTL based on search duration.

    Short search windows (2 hours) should have short TTLs (30 min).
    Long search windows (30 days) should have longer TTLs (24 hours).

    Args:
        duration: Search duration - either days (int) or timedelta

    Returns:
        TTL in hours
    """
    # Convert int (days) to timedelta for backwards compatibility
    if isinstance(duration, int):
        duration = timedelta(days=duration)

    total_hours = duration.total_seconds() / 3600

    if total_hours <= 2:
        # 2 hours or less: cache for 30 minutes
        return 0.5
    elif total_hours <= 6:
        # Up to 6 hours: cache for 1 hour
        return 1.0
    elif total_hours <= 24:
        # Up to 1 day: cache for 2 hours
        return 2.0
    elif total_hours <= 72:
        # Up to 3 days: cache for 6 hours
        return 6.0
    elif total_hours <= 168:
        # Up to 1 week: cache for 12 hours
        return 12.0
    else:
        # Longer periods: cache for 24 hours
        return DEFAULT_TTL_HOURS


def ensure_cache_dir():
    """Ensure cache directory exists with secure permissions."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)


def get_cache_key(topic: str, from_date: str, to_date: str, sources: str) -> str:
    """Generate a cache key from query parameters."""
    key_data = f"{topic}|{from_date}|{to_date}|{sources}"
    return hashlib.sha256(key_data.encode()).hexdigest()[:16]


def get_cache_path(cache_key: str) -> Path:
    """Get path to cache file."""
    return CACHE_DIR / f"{cache_key}.json"


def is_cache_valid(cache_path: Path, ttl_hours: int = DEFAULT_TTL_HOURS) -> bool:
    """Check if cache file exists and is within TTL."""
    if not cache_path.exists():
        return False

    try:
        stat = cache_path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        age_hours = (now - mtime).total_seconds() / 3600
        return age_hours < ttl_hours
    except OSError:
        return False


def load_cache(cache_key: str, ttl_hours: int = DEFAULT_TTL_HOURS) -> Optional[dict]:
    """Load data from cache if valid."""
    cache_path = get_cache_path(cache_key)

    if not is_cache_valid(cache_path, ttl_hours):
        return None

    try:
        with open(cache_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def get_cache_age_hours(cache_path: Path) -> Optional[float]:
    """Get age of cache file in hours."""
    if not cache_path.exists():
        return None
    try:
        stat = cache_path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - mtime).total_seconds() / 3600
    except OSError:
        return None


def load_cache_with_age(cache_key: str, ttl_hours: int = DEFAULT_TTL_HOURS) -> tuple:
    """Load data from cache with age info.

    Returns:
        Tuple of (data, age_hours) or (None, None) if invalid
    """
    cache_path = get_cache_path(cache_key)

    if not is_cache_valid(cache_path, ttl_hours):
        return None, None

    age = get_cache_age_hours(cache_path)

    try:
        with open(cache_path, 'r') as f:
            return json.load(f), age
    except (json.JSONDecodeError, OSError):
        return None, None


def save_cache(cache_key: str, data: dict):
    """Save data to cache."""
    ensure_cache_dir()
    cache_path = get_cache_path(cache_key)

    try:
        with open(cache_path, 'w') as f:
            json.dump(data, f)
    except OSError:
        pass  # Silently fail on cache write errors


def clear_cache():
    """Clear all cache files."""
    if CACHE_DIR.exists():
        for f in CACHE_DIR.glob("*.json"):
            try:
                f.unlink()
            except OSError:
                pass


# Model selection cache (longer TTL)
MODEL_CACHE_FILE = CACHE_DIR / "model_selection.json"


def load_model_cache() -> dict:
    """Load model selection cache."""
    if not is_cache_valid(MODEL_CACHE_FILE, MODEL_CACHE_TTL_DAYS * 24):
        return {}

    try:
        with open(MODEL_CACHE_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_model_cache(data: dict):
    """Save model selection cache."""
    ensure_cache_dir()
    try:
        with open(MODEL_CACHE_FILE, 'w') as f:
            json.dump(data, f)
    except OSError:
        pass


def get_cached_model(provider: str) -> Optional[str]:
    """Get cached model selection for a provider."""
    cache = load_model_cache()
    return cache.get(provider)


def set_cached_model(provider: str, model: str):
    """Cache model selection for a provider."""
    cache = load_model_cache()
    cache[provider] = model
    cache['updated_at'] = datetime.now(timezone.utc).isoformat()
    save_model_cache(cache)
