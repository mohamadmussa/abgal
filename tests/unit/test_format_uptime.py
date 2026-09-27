"""format_uptime, seconds as DD:HH:MM for the status table (#89)."""

import pytest

import abgal


@pytest.mark.parametrize("seconds, expected", [
    (0, "00:00:00"),
    (59, "00:00:00"),
    (60, "00:00:01"),
    (3600, "00:01:00"),
    (86400, "01:00:00"),
    (2 * 86400 + 5 * 3600 + 7 * 60 + 30, "02:05:07"),
])
def test_format_uptime(seconds, expected):
    assert abgal.format_uptime(seconds) == expected
