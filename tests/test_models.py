from __future__ import annotations

import pytest

from vpn_tester.models import Config


def test_config_empty_stats():
    c = Config(uri="vless://x@y.com:443")
    assert c.error_rate == 1.0
    assert c.avg_latency == float("inf")
    assert c.display_name() == "vless://x@y.com:443"


def test_config_display_flag():
    c = Config(
        uri="vless://x@y.com:443", name="raw", country="US", country_name="United States", flag="🇺🇸"
    )
    assert c.display_name() == "United States 🇺🇸"


def test_record_tracks_per_target():
    c = Config(uri="vless://x@y.com:443")
    c.record("YouTube", True)
    c.record("YouTube", True)
    c.record("YouTube", False)
    c.record("X.com", False)
    assert c.target_stats == {"YouTube": {"ok": 2, "fail": 1}, "X.com": {"ok": 0, "fail": 1}}


def test_weighted_error_rate():
    c = Config(uri="vless://x@y.com:443")
    c.record("YouTube", False)
    c.record("X.com", True)
    # YouTube weight 2, X.com weight 1: 2/3 of weighted traffic failed
    weights = {"YouTube": 2.0, "X.com": 1.0}
    assert c.weighted_error_rate(weights) == pytest.approx(2.0 / 3.0)
    assert c.weighted_error_rate({}) == pytest.approx(0.5)  # default weight = 1


def test_weighted_error_rate_empty():
    c = Config(uri="vless://x@y.com:443")
    assert c.weighted_error_rate({}) == 1.0
