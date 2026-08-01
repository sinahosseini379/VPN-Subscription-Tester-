"""Exit-IP geo-location with multiple fallback providers and an in-memory cache.

The HTTP-fetch functions are injectable so the module is unit-testable without
real network access or SOCKS proxies (aioresponses cannot intercept proxied
requests).
"""

from __future__ import annotations

import logging
from typing import Callable

import aiohttp

from .models import Config

log = logging.getLogger(__name__)

PROVIDERS = {
    "https://ipinfo.io/json": "ipinfo",
    "https://ip-api.com/json/": "ip_api",
    "https://ipapi.co/json/": "ipapi",
}

FetchCountry = Callable[["aiohttp.ClientSession", str, str, float], "str | None"]
FetchIp = Callable[["aiohttp.ClientSession", str, str], "str | None"]


def parse_country(payload: dict, provider: str) -> str | None:
    """Return a 2-letter uppercase country code from a provider payload."""
    if provider == "ipinfo":
        cc = payload.get("country")
    elif provider == "ip_api":
        cc = payload.get("countryCode")
        if payload.get("status") not in ("success", None):
            cc = None
    elif provider == "ipapi":
        cc = payload.get("country_code") or payload.get("country")
    else:
        cc = None
    if isinstance(cc, str) and len(cc) == 2:
        return cc.upper()
    return None


async def fetch_country(
    session: aiohttp.ClientSession, url: str, proxy: str, timeout: float
) -> str | None:
    """Query one geo-IP provider through the SOCKS proxy; return country code."""
    provider = PROVIDERS.get(url, "unknown")
    try:
        to = aiohttp.ClientTimeout(connect=timeout, total=timeout + 5)
        async with session.get(url, proxy=proxy, timeout=to, ssl=False) as resp:
            if resp.status != 200:
                return None
            payload = await resp.json(content_type=None)
        return parse_country(payload, provider)
    except Exception as exc:
        log.debug("Geo provider %s failed: %s", url, exc)
        return None


async def fetch_exit_ip(session: aiohttp.ClientSession, proxy: str, timeout: float) -> str | None:
    """Best-effort exit IP for cache keys; failure just disables caching."""
    try:
        to = aiohttp.ClientTimeout(connect=timeout, total=timeout + 5)
        async with session.get("https://api.ipify.org", proxy=proxy, timeout=to, ssl=False) as resp:
            if resp.status == 200:
                return (await resp.text()).strip()
    except Exception:
        return None
    return None


class GeoCache:
    """Cache country lookups keyed by exit IP; falls back across providers."""

    def __init__(
        self,
        urls: list[str],
        fetch: FetchCountry = fetch_country,
        fetch_ip: FetchIp = fetch_exit_ip,
    ) -> None:
        self._urls = list(urls)
        self._fetch = fetch
        self._fetch_ip = fetch_ip
        self._cache: dict[str, str] = {}

    async def get_country(
        self, session: aiohttp.ClientSession, proxy: str, timeout: float
    ) -> str | None:
        """Return exit country for the given proxy. Result is cached per IP."""
        exit_ip = await self._fetch_ip(session, proxy, timeout)
        if exit_ip:
            cached = self._cache.get(exit_ip)
            if cached:
                return cached
        for url in self._urls:
            cc = await self._fetch(session, url, proxy, timeout)
            if cc:
                if exit_ip:
                    self._cache[exit_ip] = cc
                return cc
        return None


async def check_exit_country(
    cfg: Config, session: aiohttp.ClientSession, proxy: str, cache: GeoCache, timeout: float
) -> str | None:
    """High-level helper used by the pipeline."""
    return await cache.get_country(session, proxy, timeout)
