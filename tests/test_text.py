"""Row text helpers: ages and container status."""

import pytest

from tmux_sidepanel.text import compact_status, format_age


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0s"),
        (5, "5s"),
        (59, "59s"),
        (60, "1m"),
        (119, "1m"),
        (3599, "59m"),
        (3600, "1h"),
        (86399, "23h"),
        (86400, "1d"),
        (172800, "2d"),
        (-5, "0s"),
    ],
)
def test_format_age(seconds, expected):
    assert format_age(seconds) == expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("Up 12 seconds", "12s"),
        ("Up 1 minute", "1m"),
        ("Up 6 hours", "6h"),
        ("Up 6 hours (healthy)", "6h (healthy)"),
        ("Up 6 hours (unhealthy)", "6h (unhealthy)"),
        ("Up About an hour", "1h"),
        ("Up an hour", "1h"),
        ("Up 3 days", "3d"),
        ("Up 2 weeks", "2w"),
        ("Up 4 months", "4mo"),
        ("Up 1 year", "1y"),
        ("Up Less than a second", "<1s"),
        ("Exited (0) 2 hours ago", "Exited (0) 2 hours ago"),
        ("Restarting (1) 5 seconds ago", "Restarting (1) 5 seconds ago"),
        ("", ""),
    ],
)
def test_compact_status(status, expected):
    assert compact_status(status) == expected
