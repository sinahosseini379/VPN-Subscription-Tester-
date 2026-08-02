from __future__ import annotations

import json
from pathlib import Path

from vpn_tester.config import Settings
from vpn_tester.models import Config
from vpn_tester.output import build_metadata, country_output_path, write_subscription


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


def _cfg_cc(name, cc, cc_name, flag):
    c = Config(
        uri=f"vless://x@{name}.com:443#",
        name=name,
        protocol="vless",
        server=f"{name}.com",
        port=443,
        latencies=[10.0],
        total=1,
        country=cc,
        country_name=cc_name,
        flag=flag,
    )
    return c


def test_country_output_path_derives_name():
    assert country_output_path("felfelconfig.txt", "DE") == Path("felfelconfig-DE.txt")
    assert country_output_path("out/best.txt", "US") == Path("out/best-US.txt")


def test_write_subscription_emits_per_country_files(tmp_path):
    import base64 as _b64

    de1 = _cfg_cc("de1", "DE", "Germany", "🇩🇪")
    de2 = _cfg_cc("de2", "DE", "Germany", "🇩🇪")
    us1 = _cfg_cc("us1", "US", "United States", "🇺🇸")
    for i, c in enumerate([de1, de2, us1], 1):
        c.index = i
    s = Settings(
        output_file=str(tmp_path / "felfelconfig.txt"),
        metadata_file=str(tmp_path / "felfelconfig.txt.meta.json"),
        per_country_output=True,
    )
    meta = write_subscription([de1, de2, us1], s)

    de_file = tmp_path / "felfelconfig-DE.txt"
    us_file = tmp_path / "felfelconfig-US.txt"
    assert de_file.is_file() and us_file.is_file()

    # Germany file holds exactly the two DE configs.
    de_lines = _b64.b64decode(de_file.read_text()).decode().splitlines()
    assert len(de_lines) == 2 and all("de" in ln for ln in de_lines)
    us_lines = _b64.b64decode(us_file.read_text()).decode().splitlines()
    assert len(us_lines) == 1

    # written_files lists main + meta + both country files, for the push step.
    assert str(de_file) in meta["written_files"]
    assert str(us_file) in meta["written_files"]


def test_write_subscription_per_country_disabled(tmp_path):
    de1 = _cfg_cc("de1", "DE", "Germany", "🇩🇪")
    de1.index = 1
    s = Settings(
        output_file=str(tmp_path / "felfelconfig.txt"),
        metadata_file=str(tmp_path / "felfelconfig.txt.meta.json"),
        per_country_output=False,
    )
    write_subscription([de1], s)
    assert not (tmp_path / "felfelconfig-DE.txt").exists()


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
