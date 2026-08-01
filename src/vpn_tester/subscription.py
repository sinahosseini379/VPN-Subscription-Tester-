"""Download subscriptions and extract config URIs.

Decoding logic is pure and unit-testable; the async downloader only adds I/O.
"""

from __future__ import annotations

import base64
import json
import logging
import urllib.parse
from typing import Any

import aiohttp

from .parsers import is_valid_uri

log = logging.getLogger(__name__)


def decode_subscription(text: str) -> list[str]:
    """Turn raw subscription payload (base64 / JSON / plain text) into URIs."""
    # 1) Try base64 first — the most common subscription format.
    try:
        decoded = base64.b64decode(text + "==").decode("utf-8", errors="ignore")
        if any(decoded.startswith(p) for p in ("vmess://", "vless://", "ss://", "trojan://")):
            return _unique_lines(decoded)
    except Exception:
        pass

    # 2) Try JSON (sing-box / clash / multi-format).
    try:
        obj = json.loads(text)
        uris = extract_json_uris(obj)
        if uris:
            return _unique_lines("\n".join(uris))
    except Exception:
        pass

    # 3) Plain newline-separated list.
    return _unique_lines(text)


def _unique_lines(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line and line not in seen and is_valid_uri(line):
            seen.add(line)
            out.append(line)
    return out


def extract_json_uris(obj: Any) -> list[str]:
    """Extract URIs from sing-box or Clash JSON structures."""
    uris: list[str] = []
    if isinstance(obj, dict):
        for out in obj.get("outbounds", []):  # sing-box
            u = singbox_outbound_to_uri(out)
            if u:
                uris.append(u)
        for proxy in obj.get("proxies", []):  # Clash
            u = clash_proxy_to_uri(proxy)
            if u:
                uris.append(u)
        for nested in obj.get("proxies", obj.get("configs", [])):
            if isinstance(nested, str):
                uris.append(nested)
    elif isinstance(obj, list):
        for item in obj:
            uris.extend(extract_json_uris(item))
    return uris


def singbox_outbound_to_uri(ob: dict) -> str | None:
    t = ob.get("type", "")
    server = ob.get("server", "")
    port = ob.get("server_port", 443)
    if not server:
        return None
    tag = urllib.parse.quote(str(ob.get("tag") or "config"))
    if t == "vless":
        return f"vless://{ob.get('uuid', '')}@{server}:{port}?type=tcp#{tag}"
    if t in ("shadowsocks", "ss"):
        ui = base64.b64encode(f"{ob.get('method', '')}:{ob.get('password', '')}".encode()).decode()
        return f"ss://{ui}@{server}:{port}#{tag}"
    if t == "trojan":
        return f"trojan://{ob.get('password', '')}@{server}:{port}#{tag}"
    return None


def clash_proxy_to_uri(px: dict) -> str | None:
    t = px.get("type", "")
    server = px.get("server", "")
    port = px.get("port", 443)
    if not server:
        return None
    name = urllib.parse.quote(str(px.get("name") or "config"))
    if t == "ss":
        ui = base64.b64encode(f"{px.get('cipher', '')}:{px.get('password', '')}".encode()).decode()
        return f"ss://{ui}@{server}:{port}#{name}"
    if t == "trojan":
        return f"trojan://{px.get('password', '')}@{server}:{port}#{name}"
    if t in ("vless", "vmess"):
        return f"{t}://{px.get('uuid', '')}@{server}:{port}?type=tcp#{name}"
    return None


async def fetch_subscription(
    url: str, session: aiohttp.ClientSession, timeout: float = 30.0
) -> list[str]:
    """Download one subscription and return its URIs."""
    log.info("Downloading %s", url)
    try:
        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        async with session.get(url, timeout=timeout_obj) as resp:
            if resp.status >= 400:
                log.warning("  %s -> HTTP %s", url, resp.status)
                return []
            text = await resp.text(errors="replace")
    except Exception as exc:
        log.warning("  Failed %s: %s", url, exc)
        return []

    uris = decode_subscription(text.strip())
    log.info("  %s valid configs from %s", len(uris), url)
    return uris
