from __future__ import annotations

import json

from vpn_tester.config import Settings
from vpn_tester.models import Config
from vpn_tester.output import build_metadata, write_subscription


def _cfg(name, latencies, errors=0, total=None):
    total = total if total is not None else (len(latencies) + errors)
    return Config(
        uri=f"vless://x@{name}.com:443#",
        name=name,
        protocol="vless",
        server=f"{name}.com",
        port=443,
        latencies=list(latencies),
        errors=errors,
        total=total,
        country="DE",
        country_name="Germany",
        flag="🇩🇪",
    )


def test_avg_latency_and_error_rate():
    c = _cfg("a", [100, 200], errors=1, total=3)
    assert c.avg_latency == 150.0
    assert c.error_rate == pytest_approx(1 / 3)


def pytest_approx(v):
    from pytest import approx

    return approx(v)


def test_percentiles():
    c = _cfg("a", [1, 2, 3, 4])
    assert c.p50 == 2.5
    assert c.p95 == 3.85


def test_build_metadata():
    configs = [
        _cfg("a", [100, 120], errors=0, total=2),
        _cfg("b", [200], errors=1, total=2),
    ]
    s = Settings()
    meta = build_metadata(configs, s)
    assert meta["count"] == 2
    assert meta["by_country"] == {"DE": 2}
    assert meta["items"][0]["name"] == "Germany 🇩🇪"
    assert meta["items"][0]["p50_ms"] == 110.0
    assert meta["items"][1]["error_rate"] == 0.5


def test_build_metadata_empty():
    meta = build_metadata([], Settings())
    assert meta["count"] == 0
    assert meta["avg_error_rate"] == 1.0


def test_write_subscription_roundtrip(tmp_path):
    import base64 as _b64
    from urllib.parse import unquote

    configs = [_cfg("a", [10], total=1)]
    configs[0].index = 1
    s = Settings(
        output_file=str(tmp_path / "best.txt"), metadata_file=str(tmp_path / "best.meta.json")
    )
    write_subscription(configs, s)
    out = (tmp_path / "best.txt").read_text(encoding="utf-8")
    decoded = _b64.b64decode(out).decode()
    # the URI is rewritten with a URL-encoded fragment name (Flag Country | NN)
    assert decoded.startswith("vless://x@a.com:443#")
    assert unquote(decoded.split("#", 1)[1]) == "🇩🇪 Germany | 01"
    meta = json.loads((tmp_path / "best.meta.json").read_text(encoding="utf-8"))
    assert meta["count"] == 1


def test_build_metadata_includes_index(tmp_path):
    c = _cfg("a", [100], total=1)
    c.index = 3
    s = Settings()
    meta = build_metadata([c], s)
    item = meta["items"][0]
    assert item["index"] == 3
    assert item["name"] == "🇩🇪 Germany | 03"
