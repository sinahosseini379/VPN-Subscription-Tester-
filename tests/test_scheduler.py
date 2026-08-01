from __future__ import annotations

import datetime

import pytest

from vpn_tester.main import seconds_until_next_run

# Tehran is fixed at UTC+3:30 (no DST since 2022).
TZ = "Asia/Tehran"


def _utc(*args):
    return datetime.datetime(*args, tzinfo=datetime.timezone.utc)


def test_next_run_later_same_day_tehran():
    now = _utc(2026, 8, 1, 0, 0, 0)  # 03:30 Tehran
    secs = seconds_until_next_run("04:04", now, TZ)  # next 04:04 Tehran = 00:34 UTC
    assert secs == pytest.approx(34 * 60)


def test_next_run_tomorrow_when_passed_tehran():
    now = _utc(2026, 8, 1, 1, 0, 0)  # 04:30 Tehran, already past 04:04
    secs = seconds_until_next_run("04:04", now, TZ)
    # next = tomorrow 00:34 UTC = 23h34m away
    assert secs == pytest.approx((23 * 60 + 34) * 60)


def test_next_run_exactly_at_time_is_tomorrow():
    now = _utc(2026, 8, 1, 0, 34, 0)  # exactly 04:04 Tehran
    secs = seconds_until_next_run("04:04", now, TZ)
    assert secs == pytest.approx(24 * 60 * 60)


def test_utc_timezone_semantics():
    now = _utc(2026, 8, 1, 3, 0, 0)
    secs = seconds_until_next_run("04:04", now, "UTC")
    assert secs == pytest.approx(64 * 60)


def test_naive_now_treated_as_utc():
    now = datetime.datetime(2026, 8, 1, 3, 0, 0)  # naive -> UTC
    secs = seconds_until_next_run("04:04", now, "UTC")
    assert secs == pytest.approx(64 * 60)


def test_single_digit_hour():
    now = _utc(2026, 8, 1, 0, 0, 0)  # 03:30 Tehran
    secs = seconds_until_next_run("4:04", now, TZ)
    assert secs == pytest.approx(34 * 60)


@pytest.mark.parametrize("bad", ["04:70", "25:00", "4pm", "", "abc", "10"])
def test_invalid_schedule_raises(bad):
    now = _utc(2026, 8, 1, 3, 0, 0)
    with pytest.raises(ValueError):
        seconds_until_next_run(bad, now, "UTC")


def test_unknown_timezone_raises():
    now = _utc(2026, 8, 1, 3, 0, 0)
    with pytest.raises(ValueError):
        seconds_until_next_run("04:04", now, "Mars/OlympusMons")


def test_default_schedule_and_tz():
    from vpn_tester.config import Settings

    assert Settings().schedule_time == "04:04"
    assert Settings().timezone == "Asia/Tehran"
