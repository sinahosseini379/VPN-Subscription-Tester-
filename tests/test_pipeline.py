from __future__ import annotations

from vpn_tester.config import Settings
from vpn_tester.models import Config
from vpn_tester.pipeline import select_top


def _cfg(
    name: str, country: str, latencies: list[float], errors: int = 0, total: int | None = None
):
    total = total if total is not None else len(latencies) + errors
    c = Config(
        uri=f"vless://x@{name}.com:443#",
        name=name,
        server=f"{name}.com",
        port=443,
        country=country,
        latencies=list(latencies),
        errors=errors,
        total=total,
    )
    # mirror errors/total into per-target stats so weighted_error_rate matches
    c.record("Test", False)
    c.target_stats["Test"]["ok"] = total - errors
    c.target_stats["Test"]["fail"] = errors
    return c


def test_select_top_takes_n_per_country_in_order():
    s = Settings(configs_per_country=2)
    configs = [
        _cfg("de3", "DE", [300]),
        _cfg("de1", "DE", [100]),
        _cfg("de2", "DE", [200]),
        _cfg("us1", "US", [50]),
        _cfg("us2", "US", [60]),
        _cfg("us3", "US", [70]),
        _cfg("tr1", "TR", [90]),
    ]
    top = select_top(configs, s)
    countries = [c.country for c in top]
    # order follows allowlist: DE first, then FI (none), NL (none), GB (none), US, TR
    assert countries == ["DE", "DE", "US", "US", "TR"]
    # best two per country by latency
    assert [c.name for c in top[:2]] == ["de1", "de2"]
    assert [c.name for c in top[2:4]] == ["us1", "us2"]


def test_select_top_drops_high_error_rate():
    s = Settings(configs_per_country=2, max_error_rate=0.1)
    configs = [
        _cfg("good", "DE", [100], errors=0, total=10),
        _cfg("bad", "DE", [100], errors=5, total=10),  # 50% errors -> dropped
        _cfg("ok", "DE", [120], errors=0, total=10),
    ]
    top = select_top(configs, s)
    assert [c.name for c in top] == ["good", "ok"]


def test_select_top_country_with_fewer_returns_available():
    s = Settings(configs_per_country=3)
    configs = [_cfg("de1", "DE", [100]), _cfg("us1", "US", [50])]
    top = select_top(configs, s)
    assert [c.name for c in top] == ["de1", "us1"]


def test_select_top_empty():
    assert select_top([], Settings()) == []


def test_select_top_empty_country_skipped():
    s = Settings(configs_per_country=2)
    top = select_top([_cfg("us1", "US", [50])], s)
    assert [c.name for c in top] == ["us1"]
