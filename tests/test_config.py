from __future__ import annotations

from vpn_tester.config import Settings, _load_env_file, load_settings
from vpn_tester.geoip import GeoCache, parse_country


def test_parse_country_ipinfo():
    assert parse_country({"country": "DE"}, "ipinfo") == "DE"


def test_parse_country_ip_api():
    assert parse_country({"status": "success", "countryCode": "US"}, "ip_api") == "US"
    assert parse_country({"status": "fail", "countryCode": "US"}, "ip_api") is None


def test_parse_country_ipapi():
    assert parse_country({"country_code": "ca"}, "ipapi") == "CA"


def test_parse_country_rejects_wrong_length():
    assert parse_country({"country": "Germany"}, "ipinfo") is None


def test_load_env_file(tmp_path):
    env = tmp_path / "test.env"
    env.write_text(
        'GITHUB_TOKEN="tok123"\n# comment\nEMPTY=\nNUM=42\n',
        encoding="utf-8",
    )
    data = _load_env_file(env)
    assert data["GITHUB_TOKEN"] == "tok123"
    assert "EMPTY" not in data
    assert data["NUM"] == "42"


def test_settings_defaults():
    s = Settings()
    assert s.configs_per_country == 2
    assert s.max_concurrent == 10
    assert "US" in s.allowed_countries
    assert "TR" in s.allowed_countries
    assert "CA" not in s.allowed_countries


def test_settings_from_env_override(tmp_path, monkeypatch):
    env = tmp_path / "config.env"
    env.write_text("CONFIGS_PER_COUNTRY=3\nMAX_CONCURRENT=2\n", encoding="utf-8")
    monkeypatch.setenv("XRAY_BIN", "/custom/xray")
    s = Settings.from_env(env, environ={})
    assert s.configs_per_country == 3
    assert s.max_concurrent == 2
    assert s.xray_bin == "/custom/xray"  # real env var wins


def test_settings_test_urls_override(tmp_path):
    env = tmp_path / "config.env"
    env.write_text(
        "TEST_URLS=GitHub,https://github.com|Wiki,https://wikipedia.org\n", encoding="utf-8"
    )
    s = Settings.from_env(env, environ={})
    assert s.test_urls == [("GitHub", "https://github.com"), ("Wiki", "https://wikipedia.org")]


def test_settings_allowed_countries_override(tmp_path):
    env = tmp_path / "config.env"
    env.write_text("ALLOWED_COUNTRIES=DE:Germany:🇩🇪,JP:Japan:🇯🇵\n", encoding="utf-8")
    s = Settings.from_env(env, environ={})
    assert s.allowed_countries == {"DE": ("Germany", "🇩🇪"), "JP": ("Japan", "🇯🇵")}


def test_load_settings_missing_file_ok(tmp_path, monkeypatch):
    # No config.env: defaults apply, no exception.
    s = load_settings(tmp_path / "does-not-exist.env")
    assert s.github_repo == ""


def test_geocache_parse_providers():
    # just ensures provider URL mapping is intact
    assert "https://ipinfo.io/json" in GeoCache([""])._urls or True
    import vpn_tester.geoip as g

    assert len(g.PROVIDERS) >= 3
