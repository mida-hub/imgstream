"""Tests for gallery page datetime conversion functionality."""

from datetime import datetime, timezone, timedelta
import pytest

from src.imgstream.ui.pages.gallery import convert_utc_to_jst, parse_datetime_string, JST


class TestDateTimeConversion:
    """Test datetime conversion functions."""

    def test_convert_utc_to_jst_with_utc_timezone(self):
        """Test UTC to JST conversion with UTC timezone."""
        utc_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        jst_time = convert_utc_to_jst(utc_time)

        expected_jst = datetime(2024, 1, 1, 21, 0, 0, tzinfo=JST)
        assert jst_time == expected_jst
        assert jst_time.tzinfo == JST

    def test_convert_utc_to_jst_without_timezone(self):
        """Test UTC to JST conversion without timezone (assumes UTC)."""
        naive_time = datetime(2024, 1, 1, 12, 0, 0)
        jst_time = convert_utc_to_jst(naive_time)

        expected_jst = datetime(2024, 1, 1, 21, 0, 0, tzinfo=JST)
        assert jst_time == expected_jst
        assert jst_time.tzinfo == JST

    def test_convert_utc_to_jst_with_different_timezone(self):
        """Test UTC to JST conversion with different timezone."""
        # EST timezone (UTC-5)
        est = timezone(timedelta(hours=-5))
        est_time = datetime(2024, 1, 1, 7, 0, 0, tzinfo=est)
        jst_time = convert_utc_to_jst(est_time)

        expected_jst = datetime(2024, 1, 1, 21, 0, 0, tzinfo=JST)
        assert jst_time == expected_jst
        assert jst_time.tzinfo == JST

    def test_parse_datetime_string_with_z_suffix(self):
        """Test parsing datetime string with Z suffix."""
        datetime_str = "2024-01-01T12:00:00Z"
        parsed = parse_datetime_string(datetime_str)

        expected = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert parsed == expected

    def test_parse_datetime_string_with_timezone_offset(self):
        """Test parsing datetime string with timezone offset."""
        datetime_str = "2024-01-01T12:00:00+00:00"
        parsed = parse_datetime_string(datetime_str)

        expected = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert parsed == expected

    def test_parse_datetime_string_with_jst_offset(self):
        """Test parsing datetime string with JST offset."""
        datetime_str = "2024-01-01T21:00:00+09:00"
        parsed = parse_datetime_string(datetime_str)

        expected = datetime(2024, 1, 1, 21, 0, 0, tzinfo=JST)
        assert parsed == expected

    def test_parse_datetime_string_invalid(self):
        """Test parsing invalid datetime string."""
        datetime_str = "invalid-datetime"
        parsed = parse_datetime_string(datetime_str)

        assert parsed is None

    def test_parse_datetime_string_empty(self):
        """Test parsing empty datetime string."""
        datetime_str = ""
        parsed = parse_datetime_string(datetime_str)

        assert parsed is None

    def test_full_conversion_workflow(self):
        """Test full conversion workflow from string to JST."""
        # Simulate UTC datetime string from database
        utc_string = "2024-01-01T12:00:00Z"

        # Parse the string
        parsed_utc = parse_datetime_string(utc_string)
        assert parsed_utc is not None

        # Convert to JST
        jst_time = convert_utc_to_jst(parsed_utc)

        # Verify the result
        expected_jst = datetime(2024, 1, 1, 21, 0, 0, tzinfo=JST)
        assert jst_time == expected_jst

        # Verify formatting
        formatted = jst_time.strftime('%Y-%m-%d %H:%M:%S')
        assert formatted == "2024-01-01 21:00:00"

    def test_edge_case_date_boundary(self):
        """Test date boundary conversion (UTC to JST crosses date)."""
        # 23:30 UTC should become 08:30 JST next day
        utc_string = "2024-01-01T23:30:00Z"
        parsed_utc = parse_datetime_string(utc_string)
        jst_time = convert_utc_to_jst(parsed_utc)

        expected_jst = datetime(2024, 1, 2, 8, 30, 0, tzinfo=JST)
        assert jst_time == expected_jst
