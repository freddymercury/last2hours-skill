"""Normalization of raw API data to canonical schema."""

from typing import Any, Dict, List, TypeVar, Union
from urllib.parse import urlparse

from . import dates, schema

T = TypeVar("T", schema.RedditItem, schema.XItem, schema.WebSearchItem)


def is_valid_url(url: str) -> bool:
    """Validate that a URL is a safe HTTP(S) URL.

    Security: Prevents file://, javascript:, and other dangerous schemes.
    """
    if not isinstance(url, str) or not url:
        return False
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def is_valid_reddit_url(url: str) -> bool:
    """Validate that a URL is from reddit.com.

    Security: Uses exact hostname match, not substring check.
    """
    if not is_valid_url(url):
        return False
    try:
        parsed = urlparse(url)
        # Exact hostname match to prevent SSRF via reddit.com@evil.com
        return parsed.netloc in ("reddit.com", "www.reddit.com", "old.reddit.com")
    except Exception:
        return False


def is_valid_x_url(url: str) -> bool:
    """Validate that a URL is from x.com or twitter.com."""
    if not is_valid_url(url):
        return False
    try:
        parsed = urlparse(url)
        return parsed.netloc in ("x.com", "www.x.com", "twitter.com", "www.twitter.com")
    except Exception:
        return False


def _normalize_date_for_comparison(date_str: str) -> str:
    """Normalize a date string for comparison.

    Handles both YYYY-MM-DD and ISO 8601 datetime formats.
    Returns YYYY-MM-DD portion for comparison.
    """
    if not date_str:
        return ""
    # If it's a full datetime (contains T), extract just the date part
    if "T" in date_str:
        return date_str.split("T")[0]
    return date_str


def filter_by_date_range(
    items: List[T],
    from_date: str,
    to_date: str,
    require_date: bool = False,
) -> List[T]:
    """Hard filter: Remove items outside the date range.

    This is the safety net - even if the prompt lets old content through,
    this filter will exclude it.

    Args:
        items: List of items to filter
        from_date: Start date (YYYY-MM-DD or ISO datetime) - exclude items before this
        to_date: End date (YYYY-MM-DD or ISO datetime) - exclude items after this
        require_date: If True, also remove items with no date

    Returns:
        Filtered list with only items in range (or unknown dates if not required)
    """
    # Normalize range boundaries for comparison
    from_date_normalized = _normalize_date_for_comparison(from_date)
    to_date_normalized = _normalize_date_for_comparison(to_date)

    result = []
    for item in items:
        if item.date is None:
            if not require_date:
                result.append(item)  # Keep unknown dates (with scoring penalty)
            continue

        # Normalize item date for comparison
        item_date_normalized = _normalize_date_for_comparison(item.date)

        # Hard filter: if date is before from_date, exclude
        if item_date_normalized < from_date_normalized:
            continue  # DROP - too old

        # Hard filter: if date is after to_date, exclude (likely parsing error)
        if item_date_normalized > to_date_normalized:
            continue  # DROP - future date

        result.append(item)

    return result


def normalize_reddit_items(
    items: List[Dict[str, Any]],
    from_date: str,
    to_date: str,
) -> List[schema.RedditItem]:
    """Normalize raw Reddit items to schema.

    Args:
        items: Raw Reddit items from API
        from_date: Start of date range
        to_date: End of date range

    Returns:
        List of RedditItem objects
    """
    normalized = []

    for item in items:
        # Security: Validate URL before processing
        url = item.get("url", "")
        if not is_valid_url(url):
            continue  # Skip items with invalid/dangerous URLs

        # Parse engagement
        engagement = None
        eng_raw = item.get("engagement")
        if isinstance(eng_raw, dict):
            engagement = schema.Engagement(
                score=eng_raw.get("score"),
                num_comments=eng_raw.get("num_comments"),
                upvote_ratio=eng_raw.get("upvote_ratio"),
            )

        # Parse comments (validate comment URLs too)
        top_comments = []
        for c in item.get("top_comments", []):
            comment_url = c.get("url", "")
            if comment_url and not is_valid_url(comment_url):
                comment_url = ""  # Clear invalid URLs
            top_comments.append(schema.Comment(
                score=c.get("score", 0),
                date=c.get("date"),
                author=c.get("author", ""),
                excerpt=c.get("excerpt", ""),
                url=comment_url,
            ))

        # Determine date confidence
        date_str = item.get("date")
        date_confidence = dates.get_date_confidence(date_str, from_date, to_date)

        normalized.append(schema.RedditItem(
            id=item.get("id", ""),
            title=item.get("title", ""),
            url=url,
            subreddit=item.get("subreddit", ""),
            date=date_str,
            date_confidence=date_confidence,
            engagement=engagement,
            top_comments=top_comments,
            comment_insights=item.get("comment_insights", []),
            relevance=item.get("relevance", 0.5),
            why_relevant=item.get("why_relevant", ""),
        ))

    return normalized


def normalize_x_items(
    items: List[Dict[str, Any]],
    from_date: str,
    to_date: str,
) -> List[schema.XItem]:
    """Normalize raw X items to schema.

    Args:
        items: Raw X items from API
        from_date: Start of date range
        to_date: End of date range

    Returns:
        List of XItem objects
    """
    normalized = []

    for item in items:
        # Security: Validate URL before processing
        url = item.get("url", "")
        if not is_valid_url(url):
            continue  # Skip items with invalid/dangerous URLs

        # Parse engagement
        engagement = None
        eng_raw = item.get("engagement")
        if isinstance(eng_raw, dict):
            engagement = schema.Engagement(
                likes=eng_raw.get("likes"),
                reposts=eng_raw.get("reposts"),
                replies=eng_raw.get("replies"),
                quotes=eng_raw.get("quotes"),
            )

        # Determine date confidence
        date_str = item.get("date")
        date_confidence = dates.get_date_confidence(date_str, from_date, to_date)

        normalized.append(schema.XItem(
            id=item.get("id", ""),
            text=item.get("text", ""),
            url=url,
            author_handle=item.get("author_handle", ""),
            date=date_str,
            date_confidence=date_confidence,
            engagement=engagement,
            relevance=item.get("relevance", 0.5),
            why_relevant=item.get("why_relevant", ""),
        ))

    return normalized


def items_to_dicts(items: List) -> List[Dict[str, Any]]:
    """Convert schema items to dicts for JSON serialization."""
    return [item.to_dict() for item in items]
