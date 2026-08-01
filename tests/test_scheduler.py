from __future__ import annotations

import datetime

import pytest

from vpn_tester.main import seconds_until_next_run


def test_next_run_later_today():
    now = datetime.datetime(2026, 8, 1, 3, 0, 0)
    secs = seconds_until_next_run("04:04", now)
    assert secs == pytest.approx(64 * 60)


def test_next_run_tomorrow_when_passed():
    now = datetime.datetime(2026, 8, 1, 5, 0, 0)
    secs = seconds_until_next_run("04:04", now)
    # 19h remaining today until midnight + 4h04m = 23h04m
    assert secs == pytest.approx((23 * 60 + 4) * 60)


def test_next_run_exactly_at_time_is_tomorrow():
    now = datetime.datetime(2026, 8, 1, 4, 4, 0)
    secs = seconds_until_next_run("04:04", now)
    assert secs == pytest.approx(24 * 60 * 60)


def test_next_run_single_digit_hour():
    now = datetime.datetime(2026, 8, 1, 0, 0, 0)
    secs = seconds_until_next_run("4:04", now)
    assert secs == pytest.approx(4 * 60 * 60 + 4 * 60)


@pytest.mark.parametrize("bad", ["04:70", "25:00", "4pm", "", "abc", "10"])
def test_invalid_schedule_raises(bad):
    now = datetime.datetime(2026, 8, 1, 3, 0, 0)
    with pytest.raises(ValueError):
        seconds_until_next_run(bad, now)


def test_default_schedule_is_0404():
    from vpn_tester.config import Settings

    assert Settings().schedule_time == "04:04"
