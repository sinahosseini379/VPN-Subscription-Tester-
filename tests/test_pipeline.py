from __future__ import annotations

import base64
import json

from vpn_tester.config import Settings
from vpn_tester.models import Config
from vpn_tester.pipeline import assign_indices, load_previous_configs, merge_incremental, select_top


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


def test_assign_indices_global_numbering():
    configs = [_cfg("de", "DE", [50]), _cfg("us", "US", [60]), _cfg("tr", "TR", [70])]
    assign_indices(configs)
    assert [c.index for c in configs] == [1, 2, 3]
    assert configs[0].display_name() == "DE | 01"
    assert configs[2].display_name() == "TR | 03"


def test_load_previous_configs(tmp_path):
    uris = ["vless://a@x.com:443#A", "vless://b@y.com:443#B"]
    out = tmp_path / "best.txt"
    out.write_text(base64.b64encode("\n".join(uris).encode()).decode(), encoding="utf-8")
    meta = tmp_path / "best.txt.meta.json"
    meta.write_text(
        json.dumps(
            {
                "items": [
                    {"country": "DE", "country_name": "Germany", "index": 1},
                    {"country": "US", "country_name": "United States", "index": 2},
                ]
            }
        ),
        encoding="utf-8",
    )
    s = Settings(output_file=str(out), metadata_file=str(meta))
    prev = load_previous_configs(s)
    assert len(prev) == 2
    assert prev[0].uri == uris[0]
    assert prev[0].country == "DE"
    assert prev[0].index == 1


def test_load_previous_configs_missing_file(tmp_path):
    s = Settings(output_file=str(tmp_path / "nope.txt"), metadata_file=str(tmp_path / "nope.meta"))
    assert load_previous_configs(s) == []


def test_load_previous_configs_bad_base64(tmp_path):
    out = tmp_path / "best.txt"
    out.write_text("!!!not-base64!!!", encoding="utf-8")
    s = Settings(output_file=str(out), metadata_file=str(tmp_path / "m.meta"))
    assert load_previous_configs(s) == []


def test_merge_incremental_prefers_previous_and_dedupes():
    s = Settings(configs_per_country=2)  # 6 countries -> cap 12
    old = [_cfg("old1", "DE", [10]), _cfg("old2", "DE", [20])]
    new = [_cfg("old1", "DE", [99]), _cfg("new1", "US", [30]), _cfg("new2", "TR", [40])]
    merged = merge_incremental(new, old, s)
    # old1 (from previous) wins the dedupe and comes first
    assert [c.name for c in merged] == ["old1", "old2", "new1", "new2"]
    assert len(merged) == 4


def test_merge_incremental_caps_output():
    s = Settings(configs_per_country=1)  # 6 countries -> cap 6
    old = [_cfg(f"old{i}", "DE", [10]) for i in range(5)]
    new = [_cfg(f"new{i}", "US", [10]) for i in range(5)]
    merged = merge_incremental(new, old, s)
    assert len(merged) == 6
