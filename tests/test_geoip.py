from __future__ import annotations

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


async def _fake_fetch(results):
    """Factory: returns a fetch function yielding countries one at a time."""

    async def fetch(session, url, timeout):
        try:
            return results.pop(0)
        except IndexError:
            return None

    return fetch


async def _fake_ip(ip):
    async def fetch_ip(session, timeout):
        return ip

    return fetch_ip


async def test_geocache_uses_first_provider():
    fetch = await _fake_fetch(["DE", "US"])
    ip = await _fake_ip("1.1.1.1")
    cache = GeoCache(["https://ipinfo.io/json", "https://ipapi.co/json/"], fetch=fetch, fetch_ip=ip)
    cc = await cache.get_country(None, 5)
    assert cc == "DE"


async def test_geocache_falls_back():
    fetch = await _fake_fetch([None, "CA"])
    ip = await _fake_ip("1.1.1.1")
    cache = GeoCache(["https://ipinfo.io/json", "https://ipapi.co/json/"], fetch=fetch, fetch_ip=ip)
    cc = await cache.get_country(None, 5)
    assert cc == "CA"


async def test_geocache_caches_by_ip():
    """Second call returns cached result without hitting providers again."""
    calls = {"n": 0}

    async def fetch(session, url, timeout):
        calls["n"] += 1
        return "NL"

    ip = await _fake_ip("1.2.3.4")
    cache = GeoCache(["https://ipinfo.io/json"], fetch=fetch, fetch_ip=ip)

    first = await cache.get_country(None, 5)
    second = await cache.get_country(None, 5)
    assert first == second == "NL"
    assert calls["n"] == 1


async def test_geocache_all_providers_down():
    fetch = await _fake_fetch([None, None])
    ip = await _fake_ip("1.2.3.4")
    cache = GeoCache(["a", "b"], fetch=fetch, fetch_ip=ip)
    assert await cache.get_country(None, 5) is None
