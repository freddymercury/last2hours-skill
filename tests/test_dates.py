"""Tests for dates module."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import dates


class TestGetDateRange(unittest.TestCase):
    def test_returns_tuple_of_two_strings(self):
        from_date, to_date = dates.get_date_range(30)
        self.assertIsInstance(from_date, str)
        self.assertIsInstance(to_date, str)

    def test_date_format(self):
        from_date, to_date = dates.get_date_range(30)
        # Should be YYYY-MM-DD format
        self.assertRegex(from_date, r'^\d{4}-\d{2}-\d{2}$')
        self.assertRegex(to_date, r'^\d{4}-\d{2}-\d{2}$')

    def test_range_is_correct_days(self):
        from_date, to_date = dates.get_date_range(30)
        start = datetime.strptime(from_date, "%Y-%m-%d")
        end = datetime.strptime(to_date, "%Y-%m-%d")
        delta = end - start
        self.assertEqual(delta.days, 30)


class TestParseDate(unittest.TestCase):
    def test_parse_iso_date(self):
        result = dates.parse_date("2026-01-15")
        self.assertIsNotNone(result)
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 15)

    def test_parse_timestamp(self):
        # Unix timestamp for 2026-01-15 00:00:00 UTC
        result = dates.parse_date("1768435200")
        self.assertIsNotNone(result)

    def test_parse_none(self):
        result = dates.parse_date(None)
        self.assertIsNone(result)

    def test_parse_empty_string(self):
        result = dates.parse_date("")
        self.assertIsNone(result)


class TestTimestampToDate(unittest.TestCase):
    def test_valid_timestamp(self):
        # 2026-01-15 00:00:00 UTC
        result = dates.timestamp_to_date(1768435200)
        self.assertEqual(result, "2026-01-15")

    def test_none_timestamp(self):
        result = dates.timestamp_to_date(None)
        self.assertIsNone(result)


class TestGetDateConfidence(unittest.TestCase):
    def test_high_confidence_in_range(self):
        result = dates.get_date_confidence("2026-01-15", "2026-01-01", "2026-01-31")
        self.assertEqual(result, "high")

    def test_low_confidence_before_range(self):
        result = dates.get_date_confidence("2025-12-15", "2026-01-01", "2026-01-31")
        self.assertEqual(result, "low")

    def test_low_confidence_no_date(self):
        result = dates.get_date_confidence(None, "2026-01-01", "2026-01-31")
        self.assertEqual(result, "low")


class TestDaysAgo(unittest.TestCase):
    def test_today(self):
        today = datetime.now(timezone.utc).date().isoformat()
        result = dates.days_ago(today)
        self.assertEqual(result, 0)

    def test_none_date(self):
        result = dates.days_ago(None)
        self.assertIsNone(result)


class TestRecencyScore(unittest.TestCase):
    def test_today_is_near_100(self):
        # Date-only format parses to midnight UTC, so score may not be exactly 100
        today = datetime.now(timezone.utc).date().isoformat()
        result = dates.recency_score(today)
        self.assertGreaterEqual(result, 96)  # Within 24 hours = at least 96%

    def test_30_days_ago_is_0(self):
        old_date = (datetime.now(timezone.utc).date() - timedelta(days=30)).isoformat()
        result = dates.recency_score(old_date)
        self.assertEqual(result, 0)

    def test_15_days_ago_is_near_50(self):
        # Date-only format parses to midnight UTC, so score may not be exactly 50
        mid_date = (datetime.now(timezone.utc).date() - timedelta(days=15)).isoformat()
        result = dates.recency_score(mid_date)
        self.assertGreaterEqual(result, 46)
        self.assertLessEqual(result, 54)

    def test_none_date_is_0(self):
        result = dates.recency_score(None)
        self.assertEqual(result, 0)

    def test_with_timedelta_max_duration(self):
        # 1 hour ago with 2 hour max should be ~50
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        result = dates.recency_score(one_hour_ago, timedelta(hours=2))
        self.assertGreater(result, 45)
        self.assertLess(result, 55)

    def test_with_timedelta_at_max(self):
        # 2 hours ago with 2 hour max should be 0
        two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        result = dates.recency_score(two_hours_ago, timedelta(hours=2))
        self.assertEqual(result, 0)


class TestParseRange(unittest.TestCase):
    def test_parse_hours(self):
        result = dates.parse_range("2 hours")
        self.assertEqual(result, timedelta(hours=2))

    def test_parse_hours_compact(self):
        result = dates.parse_range("2h")
        self.assertEqual(result, timedelta(hours=2))

    def test_parse_days(self):
        result = dates.parse_range("3 days")
        self.assertEqual(result, timedelta(days=3))

    def test_parse_days_compact(self):
        result = dates.parse_range("3d")
        self.assertEqual(result, timedelta(days=3))

    def test_parse_weeks(self):
        result = dates.parse_range("2 weeks")
        self.assertEqual(result, timedelta(weeks=2))

    def test_parse_weeks_compact(self):
        result = dates.parse_range("2w")
        self.assertEqual(result, timedelta(weeks=2))

    def test_parse_months(self):
        result = dates.parse_range("6 months")
        self.assertEqual(result, timedelta(days=180))  # 6 * 30 days

    def test_parse_months_compact(self):
        result = dates.parse_range("6mo")
        self.assertEqual(result, timedelta(days=180))

    def test_parse_singular(self):
        result = dates.parse_range("1 hour")
        self.assertEqual(result, timedelta(hours=1))

    def test_invalid_format_raises(self):
        with self.assertRaises(ValueError):
            dates.parse_range("invalid")

    def test_invalid_unit_raises(self):
        with self.assertRaises(ValueError):
            dates.parse_range("5 seconds")


class TestGetDateRangeWithTimedelta(unittest.TestCase):
    def test_short_duration_returns_datetime(self):
        from_date, to_date = dates.get_date_range(timedelta(hours=2))
        # Should contain 'T' for datetime format
        self.assertIn("T", from_date)
        self.assertIn("T", to_date)

    def test_long_duration_returns_date_only(self):
        from_date, to_date = dates.get_date_range(timedelta(days=7))
        # Should be YYYY-MM-DD format (no T)
        self.assertNotIn("T", from_date)
        self.assertNotIn("T", to_date)
        self.assertRegex(from_date, r'^\d{4}-\d{2}-\d{2}$')

    def test_backwards_compat_with_int(self):
        from_date, to_date = dates.get_date_range(30)
        self.assertIsInstance(from_date, str)
        self.assertIsInstance(to_date, str)


class TestGetRangeLabel(unittest.TestCase):
    def test_hours_label(self):
        result = dates.get_range_label(timedelta(hours=2))
        self.assertEqual(result, "last 2 hours")

    def test_single_hour_label(self):
        result = dates.get_range_label(timedelta(hours=1))
        self.assertEqual(result, "last 1 hour")

    def test_days_label(self):
        result = dates.get_range_label(timedelta(days=3))
        self.assertEqual(result, "last 3 days")

    def test_weeks_label(self):
        result = dates.get_range_label(timedelta(weeks=2))
        self.assertEqual(result, "last 2 weeks")

    def test_months_label(self):
        result = dates.get_range_label(timedelta(days=60))
        self.assertEqual(result, "last 2 months")


class TestGetDateConfidenceWithDatetime(unittest.TestCase):
    def test_handles_iso_datetime(self):
        # Date within range (using datetime format)
        result = dates.get_date_confidence(
            "2026-01-15",
            "2026-01-01T00:00:00+00:00",
            "2026-01-31T23:59:59+00:00"
        )
        self.assertEqual(result, "high")

    def test_handles_mixed_formats(self):
        # Date-only item date, datetime range boundaries
        result = dates.get_date_confidence(
            "2026-01-15",
            "2026-01-01T12:00:00Z",
            "2026-01-31T12:00:00Z"
        )
        self.assertEqual(result, "high")


if __name__ == "__main__":
    unittest.main()
