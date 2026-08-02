"""Exit-IP geo-location with multiple fallback providers and an in-memory cache.

The HTTP-fetch functions are injectable so the module is unit-testable without
real network access or SOCKS proxies (aioresponses cannot intercept proxied
requests).
"""

from __future__ import annotations

import logging
from typing import Callable
from urllib.parse import urlsplit

import aiohttp

from .models import Config

log = logging.getLogger(__name__)

# Ordered by reliability. ip-api.com's free tier is HTTP-only (HTTPS needs a
# paid plan), so its URL deliberately uses http:// and it sits last as a fallback.
PROVIDERS = {
    "https://ipinfo.io/json": "ipinfo",
    "https://ipapi.co/json/": "ipapi",
    "http://ip-api.com/json/": "ip_api",
}

# Provider identity is keyed off the host, so the same parser is picked whether
# the URL uses http/https or a slightly different path. Keeping this in sync with
# PROVIDERS above is what stops a default like "https://ip-api.com/..." from
# being treated as an unknown provider and silently failing to parse.
_PROVIDER_BY_HOST = {
    "ipinfo.io": "ipinfo",
    "ipapi.co": "ipapi",
    "ip-api.com": "ip_api",
}


def provider_for_url(url: str) -> str:
    """Identify the geo-IP provider from a URL by its host (scheme-agnostic)."""
    host = urlsplit(url).hostname or ""
    return _PROVIDER_BY_HOST.get(host.lower(), "unknown")


FetchCountry = Callable[["aiohttp.ClientSession", str, float], "str | None"]
FetchIp = Callable[["aiohttp.ClientSession", float], "str | None"]


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


async def fetch_country(session: aiohttp.ClientSession, url: str, timeout: float) -> str | None:
    """Query one geo-IP provider through the session's SOCKS tunnel."""
    provider = provider_for_url(url)
    try:
        to = aiohttp.ClientTimeout(connect=timeout, total=timeout + 5)
        async with session.get(url, timeout=to, ssl=False) as resp:
            if resp.status != 200:
                return None
            payload = await resp.json(content_type=None)
        return parse_country(payload, provider)
    except Exception as exc:
        log.debug("Geo provider %s failed: %s", url, exc)
        return None


async def fetch_exit_ip(session: aiohttp.ClientSession, timeout: float) -> str | None:
    """Best-effort exit IP for cache keys; failure just disables caching."""
    try:
        to = aiohttp.ClientTimeout(connect=timeout, total=timeout + 5)
        async with session.get("https://api.ipify.org", timeout=to, ssl=False) as resp:
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

    async def get_country(self, session: aiohttp.ClientSession, timeout: float) -> str | None:
        """Return exit country for the given tunnel. Result is cached per IP."""
        exit_ip = await self._fetch_ip(session, timeout)
        if exit_ip:
            cached = self._cache.get(exit_ip)
            if cached:
                return cached
        for url in self._urls:
            cc = await self._fetch(session, url, timeout)
            if cc:
                if exit_ip:
                    self._cache[exit_ip] = cc
                return cc
        return None


async def check_exit_country(
    cfg: Config, session: aiohttp.ClientSession, cache: GeoCache, timeout: float
) -> str | None:
    """High-level helper used by the pipeline."""
    return await cache.get_country(session, timeout)
