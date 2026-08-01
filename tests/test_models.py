from __future__ import annotations

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
