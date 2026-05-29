#!/usr/bin/env python3
"""
VPN Subscription Tester — Real URL Test via Xray-core
Each config gets its own Xray process with a local SOCKS5 port.
HTTP requests are routed through that proxy to measure true end-to-end latency.
"""

import asyncio
import base64
import json
import logging
import os
import random
import re
import shutil
import signal
import sys
import tempfile
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


import socket
from datetime import datetime
import github_push

import aiohttp

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("vpn_tester.log", mode="a", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ─── Test targets ─────────────────────────────────────────────────────────
TEST_URLS: list[tuple[str, str]] = [
    ("Google",     "http://www.gstatic.com/generate_204"),
    ("YouTube",    "https://www.youtube.com/generate_204"),
    ("Cloudflare", "http://cp.cloudflare.com/"),
    ("X.com",      "https://x.com/"),
]

# ─── Tunables ─────────────────────────────────────────────────────────────
TOP_N             = 10      # keep best N configs in final output
MAX_ERROR_RATE    = 0.10    # round-1 filter: drop configs with >10% errors
EXTRA_ROUNDS      = 3       # latency rounds after the filter round
PING_TRIES        = 5       # number of TCP ping attempts per config
PING_MIN_SUCCESS  = 4       # minimum successful pings required to keep config
URL_TEST_ROUNDS   = 5       # repeat URL tests this many times per config
AUTOUPDATE_MINUTES = 120    # metadata value: autoupdate interval for final settings
LOOP_INTERVAL_MINUTES = 90  # restart whole pipeline every 90 minutes
# Allowed exit country codes and emoji/name mapping
ALLOWED_COUNTRIES = {
    "DE": ("Germany", "🇩🇪"),
    "FI": ("Finland", "🇫🇮"),
    "NL": ("Netherlands", "🇳🇱"),
    "GB": ("United Kingdom", "🇬🇧"),
    "US": ("United States", "🇺🇸"),
    "CA": ("Canada", "🇨🇦"),
}
CONNECT_TIMEOUT   = 10.0    # seconds — TCP connect to proxy
REQUEST_TIMEOUT   = 15.0    # seconds — full HTTP response
MAX_CONCURRENT    = 10      # how many Xray processes run simultaneously
XRAY_STARTUP_WAIT = 1.5     # seconds to wait after launching Xray
SOCKS_PORT_BASE   = 20000   # starting SOCKS port (each worker gets a unique one)


# ─── Data model ──────────────────────────────────────────────────────────
@dataclass
class Config:
    raw: str                           # original URI line
    name: str = ""
    latencies: list[float] = field(default_factory=list)
    errors: int = 0
    total: int = 0

    @property
    def avg_latency(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else 9_999.0

    @property
    def error_rate(self) -> float:
        return self.errors / self.total if self.total else 1.0


# ─── Xray binary locator ─────────────────────────────────────────────────
def find_xray() -> str:
    """Return path to xray binary or raise."""
    candidates = [
        os.environ.get("XRAY_BIN", ""),
        "xray",
        "/usr/local/bin/xray",
        "/usr/bin/xray",
        str(Path.home() / ".local/bin/xray"),
        str(Path(__file__).parent / "xray"),
        str(Path(__file__).parent / "bin/xray"),
    ]
    for c in candidates:
        if c and shutil.which(c):
            return shutil.which(c)
    raise FileNotFoundError(
        "xray binary not found!\n"
        "Install it: https://github.com/XTLS/Xray-core/releases\n"
        "Or set XRAY_BIN=/path/to/xray environment variable."
    )


# ─── Xray config builder ─────────────────────────────────────────────────
def build_xray_config(uri: str, socks_port: int) -> Optional[dict]:
    """
    Parse a proxy URI and generate a minimal Xray JSON config that exposes a
    local SOCKS5 inbound on 127.0.0.1:socks_port forwarding to that proxy.

    Supports: vmess, vless, trojan, shadowsocks (ss://)
    Transports: tcp, ws, grpc, h2, httpupgrade, splithttp
    Security: none, tls, reality
    """
    def _strip_frag(u: str) -> str:
        return u.split("#")[0]

    def _parse_qs(s: str) -> dict:
        return dict(urllib.parse.parse_qsl(s))

    outbound: Optional[dict] = None

    # ── VLESS ─────────────────────────────────────────────────────────
    if uri.startswith("vless://"):
        u = _strip_frag(uri[8:])
        qs = ""
        if "?" in u:
            u, qs = u.split("?", 1)
        uuid, hostport = u.rsplit("@", 1)
        host, port_str = hostport.rsplit(":", 1)
        p = _parse_qs(qs)
        stream = _build_stream(p)
        outbound = {
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": host,
                    "port": int(port_str),
                    "users": [{
                        "id": uuid,
                        "encryption": "none",
                        "flow": p.get("flow", "")
                    }]
                }]
            },
            "streamSettings": stream,
        }

    # ── VMESS ─────────────────────────────────────────────────────────
    elif uri.startswith("vmess://"):
        try:
            data = json.loads(base64.b64decode(uri[8:] + "==").decode(errors="ignore"))
        except Exception:
            return None
        p = {
            "type":     data.get("net", "tcp"),
            "security": data.get("tls", "none"),
            "host":     data.get("host", data.get("add", "")),
            "path":     data.get("path", "/"),
            "sni":      data.get("sni", data.get("host", data.get("add", ""))),
            "fp":       data.get("fp", ""),
        }
        stream = _build_stream(p)
        outbound = {
            "protocol": "vmess",
            "settings": {
                "vnext": [{
                    "address": data["add"],
                    "port": int(data["port"]),
                    "users": [{
                        "id": data["id"],
                        "alterId": int(data.get("aid", 0)),
                        "security": data.get("scy", "auto"),
                    }]
                }]
            },
            "streamSettings": stream,
        }

    # ── TROJAN ────────────────────────────────────────────────────────
    elif uri.startswith("trojan://"):
        u = _strip_frag(uri[9:])
        qs = ""
        if "?" in u:
            u, qs = u.split("?", 1)
        password, hostport = u.rsplit("@", 1)
        host, port_str = hostport.rsplit(":", 1)
        p = _parse_qs(qs)
        p.setdefault("security", "tls")
        stream = _build_stream(p)
        outbound = {
            "protocol": "trojan",
            "settings": {
                "servers": [{
                    "address": host,
                    "port": int(port_str),
                    "password": password,
                }]
            },
            "streamSettings": stream,
        }

    # ── SHADOWSOCKS ───────────────────────────────────────────────────
    elif uri.startswith(("ss://", "shadowsocks://")):
        prefix = "shadowsocks://" if uri.startswith("shadowsocks://") else "ss://"
        u = _strip_frag(uri[len(prefix):])
        qs = ""
        if "?" in u:
            u, qs = u.split("?", 1)

        if "@" in u:
            userinfo, hostport = u.rsplit("@", 1)
            try:
                userinfo = base64.b64decode(userinfo + "==").decode(errors="ignore")
            except Exception:
                userinfo = urllib.parse.unquote(userinfo)
            method, password = userinfo.split(":", 1)
            host, port_str = hostport.rsplit(":", 1)
        else:
            try:
                decoded = base64.b64decode(u + "==").decode(errors="ignore")
                rest, hostport = decoded.rsplit("@", 1)
                method, password = rest.split(":", 1)
                host, port_str = hostport.rsplit(":", 1)
            except Exception:
                return None

        outbound = {
            "protocol": "shadowsocks",
            "settings": {
                "servers": [{
                    "address": host,
                    "port": int(port_str),
                    "method": method,
                    "password": password,
                }]
            },
            "streamSettings": {"network": "tcp"},
        }

    if outbound is None:
        return None

    outbound["tag"] = "proxy"

    return {
        "log": {"loglevel": "none"},
        "inbounds": [{
            "tag": "socks-in",
            "port": socks_port,
            "listen": "127.0.0.1",
            "protocol": "socks",
            "settings": {"udp": False},
            "sniffing": {"enabled": False},
        }],
        "outbounds": [
            outbound,
            {"tag": "direct", "protocol": "freedom"},
            {"tag": "block",  "protocol": "blackhole"},
        ],
        "routing": {
            "rules": [{
                "type": "field",
                "network": "tcp,udp",
                "outboundTag": "proxy",
            }]
        },
        "policy": {
            "levels": {"0": {"handshake": 4, "connIdle": 30}},
            "system": {"statsOutboundUplink": False, "statsOutboundDownlink": False},
        },
    }


def _build_stream(p: dict) -> dict:
    """Build Xray streamSettings from URI query parameters."""
    net      = p.get("type", p.get("net", "tcp"))
    security = p.get("security", p.get("tls", "none"))
    sni      = p.get("sni", p.get("host", ""))
    host     = p.get("host", "")
    path     = urllib.parse.unquote(p.get("path", "/"))
    fp       = p.get("fp", "")
    pbk      = p.get("pbk", "")
    sid      = p.get("sid", "")
    spx      = urllib.parse.unquote(p.get("spx", ""))

    stream: dict = {"network": net}

    if net == "ws":
        stream["wsSettings"] = {
            "path": path,
            "headers": {"Host": host} if host else {},
        }
    elif net == "grpc":
        stream["grpcSettings"] = {
            "serviceName": p.get("serviceName", p.get("path", "")),
            "multiMode": False,
        }
    elif net == "h2":
        stream["httpSettings"] = {
            "path": path,
            "host": [h.strip() for h in host.split(",")] if host else [],
        }
    elif net == "httpupgrade":
        stream["httpupgradeSettings"] = {"path": path, "host": host}
    elif net == "splithttp":
        stream["splithttpSettings"] = {"path": path, "host": host}
    elif net == "tcp":
        header_type = p.get("headerType", "none")
        if header_type == "http":
            stream["tcpSettings"] = {
                "header": {
                    "type": "http",
                    "request": {
                        "path": [path],
                        "headers": {"Host": [host]},
                    },
                }
            }

    if security == "tls":
        stream["security"] = "tls"
        tls: dict = {"allowInsecure": False}
        if sni:               tls["serverName"] = sni
        if fp:                tls["fingerprint"] = fp
        if p.get("alpn"):     tls["alpn"] = p["alpn"].split(",")
        stream["tlsSettings"] = tls
    elif security == "reality":
        stream["security"] = "reality"
        stream["realitySettings"] = {
            "serverName":  sni,
            "fingerprint": fp or "chrome",
            "publicKey":   pbk,
            "shortId":     sid,
            "spiderX":     spx,
        }
    else:
        stream["security"] = "none"

    return stream


# ─── Subscription downloader ─────────────────────────────────────────────
async def fetch_subscription(url: str, session: aiohttp.ClientSession) -> list[str]:
    log.info(f"↓ Downloading: {url}")
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            text = await resp.text()
    except Exception as e:
        log.warning(f"  ✗ Failed: {e}")
        return []
    lines = _decode_subscription(text.strip())
    valid = [l for l in lines if _is_valid_uri(l)]
    log.info(f"  ✓ {len(valid)} valid configs")
    return valid


def _decode_subscription(text: str) -> list[str]:
    """Handle base64-encoded, plain-text, or JSON subscription content."""
    # Try base64
    try:
        decoded = base64.b64decode(text + "==").decode("utf-8", errors="ignore")
        if any(decoded.startswith(p) for p in ("vmess://", "vless://", "ss://", "trojan://")):
            return [l.strip() for l in decoded.splitlines() if l.strip()]
    except Exception:
        pass
    # Try JSON (sing-box / clash)
    try:
        obj = json.loads(text)
        uris = _extract_json_uris(obj)
        if uris:
            return uris
    except Exception:
        pass
    # Plain list
    return [l.strip() for l in text.splitlines() if l.strip()]


def _extract_json_uris(obj) -> list[str]:
    uris = []
    if isinstance(obj, dict):
        for ob in obj.get("outbounds", []):
            u = _singbox_outbound_to_uri(ob)
            if u:
                uris.append(u)
        for px in obj.get("proxies", []):
            u = _clash_proxy_to_uri(px)
            if u:
                uris.append(u)
    elif isinstance(obj, list):
        for item in obj:
            uris.extend(_extract_json_uris(item))
    return uris


def _singbox_outbound_to_uri(ob: dict) -> Optional[str]:
    t    = ob.get("type", "")
    tag  = urllib.parse.quote(ob.get("tag", "config"))
    srv  = ob.get("server", "")
    port = ob.get("server_port", 443)
    if t == "vless":
        return f"vless://{ob.get('uuid','')}@{srv}:{port}?type=tcp#{tag}"
    if t in ("shadowsocks", "ss"):
        ui = base64.b64encode(f"{ob.get('method','')}:{ob.get('password','')}".encode()).decode()
        return f"ss://{ui}@{srv}:{port}#{tag}"
    if t == "trojan":
        return f"trojan://{ob.get('password','')}@{srv}:{port}#{tag}"
    return None


def _clash_proxy_to_uri(px: dict) -> Optional[str]:
    t    = px.get("type", "")
    name = urllib.parse.quote(px.get("name", "config"))
    srv  = px.get("server", "")
    port = px.get("port", 443)
    if t == "ss":
        ui = base64.b64encode(f"{px.get('cipher','')}:{px.get('password','')}".encode()).decode()
        return f"ss://{ui}@{srv}:{port}#{name}"
    if t == "trojan":
        return f"trojan://{px.get('password','')}@{srv}:{port}#{name}"
    if t in ("vless", "vmess"):
        return f"{t}://{px.get('uuid','')}@{srv}:{port}?type=tcp#{name}"
    return None


def _is_valid_uri(line: str) -> bool:
    PREFIXES = ("vmess://", "vless://", "ss://", "trojan://",
                "shadowsocks://", "tuic://", "hy2://", "hysteria2://")
    return any(line.startswith(p) for p in PREFIXES)


def _parse_name(uri: str) -> str:
    if "#" in uri:
        return urllib.parse.unquote(uri.split("#", 1)[1])
    if uri.startswith("vmess://"):
        try:
            data = json.loads(base64.b64decode(uri[8:] + "==").decode())
            return data.get("ps", data.get("add", "vmess"))
        except Exception:
            pass
    return uri[:50]


# ─── Per-config URL tester ────────────────────────────────────────────────
class XrayRunner:
    """
    Manages one Xray process for a single config.
    Launches Xray, runs URL tests through its SOCKS5 port, then kills it.
    """

    def __init__(self, xray_bin: str, cfg: Config, socks_port: int):
        self.xray_bin   = xray_bin
        self.cfg        = cfg
        self.socks_port = socks_port
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._tmpdir: Optional[str] = None

    async def __aenter__(self):
        xray_cfg = build_xray_config(self.cfg.raw, self.socks_port)
        if xray_cfg is None:
            raise ValueError("Cannot parse URI")
        self._tmpdir = tempfile.mkdtemp(prefix="xray_")
        cfg_path = os.path.join(self._tmpdir, "config.json")
        with open(cfg_path, "w") as f:
            json.dump(xray_cfg, f)

        self._proc = await asyncio.create_subprocess_exec(
            self.xray_bin, "run", "-config", cfg_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.sleep(XRAY_STARTUP_WAIT)
        return self

    async def __aexit__(self, *_):
        if self._proc:
            try:
                self._proc.kill()
                await asyncio.wait_for(self._proc.wait(), timeout=3)
            except Exception:
                pass
        if self._tmpdir:
            import shutil as _sh
            _sh.rmtree(self._tmpdir, ignore_errors=True)

    async def test_url(self, label: str, url: str) -> Optional[float]:
        """Send one HTTP request through the SOCKS5 proxy. Returns latency ms or None."""
        proxy_url = f"socks5://127.0.0.1:{self.socks_port}"
        connector = aiohttp.TCPConnector(ssl=False)
        timeout   = aiohttp.ClientTimeout(connect=CONNECT_TIMEOUT, total=REQUEST_TIMEOUT)
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                t0 = time.perf_counter()
                async with session.get(url, proxy=proxy_url, timeout=timeout,
                                       allow_redirects=True) as resp:
                    await resp.read()
                return (time.perf_counter() - t0) * 1000
        except Exception:
            return None

    async def run_all_tests(self) -> None:
        """Test all TEST_URLS once and record results in self.cfg."""
        tasks = [self.test_url(label, url) for label, url in TEST_URLS]
        results = await asyncio.gather(*tasks)
        for ms in results:
            self.cfg.total += 1
            if ms is None:
                self.cfg.errors += 1
            else:
                self.cfg.latencies.append(ms)

    async def get_exit_country(self) -> Optional[str]:
        """Return two-letter country code for the current exit IP (e.g. 'DE')."""
        proxy_url = f"socks5://127.0.0.1:{self.socks_port}"
        timeout = aiohttp.ClientTimeout(connect=CONNECT_TIMEOUT, total=REQUEST_TIMEOUT)
        connector = aiohttp.TCPConnector(ssl=False)
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get("https://ipapi.co/json/", proxy=proxy_url, timeout=timeout) as resp:
                    data = await resp.json()
                    cc = data.get("country_code") or data.get("country")
                    if isinstance(cc, str):
                        return cc.upper()
        except Exception:
            return None
        return None


# ─── Semaphore-limited tester ─────────────────────────────────────────────
async def test_one(xray_bin: str, cfg: Config, port: int,
                   sem: asyncio.Semaphore) -> None:
    async with sem:
        try:
            async with XrayRunner(xray_bin, cfg, port) as runner:
                await runner.run_all_tests()
        except Exception as e:
            log.debug(f"  [SKIP] {cfg.name[:40]}: {e}")
            cfg.errors += len(TEST_URLS)
            cfg.total  += len(TEST_URLS)


def _assign_ports(configs: list[Config]) -> dict[int, int]:
    """Give each config a unique SOCKS port."""
    return {i: SOCKS_PORT_BASE + i for i in range(len(configs))}


def _extract_server_from_xray_cfg(xcfg: dict) -> Optional[tuple[str, int]]:
    """Attempt to pull server address and port from an Xray outbound dict."""
    try:
        out = xcfg.get("outbounds", [])[0]
        proto = out.get("protocol", "")
        sets = out.get("settings", {})
        if proto in ("vless", "vmess"):
            vnext = sets.get("vnext", [])
            if vnext:
                addr = vnext[0].get("address")
                port = int(vnext[0].get("port", 0))
                return addr, port
        if proto == "shadowsocks":
            sv = sets.get("servers", [])[0]
            return sv.get("address"), int(sv.get("port", 0))
        if proto == "trojan":
            sv = sets.get("servers", [])[0]
            return sv.get("address"), int(sv.get("port", 0))
    except Exception:
        return None
    return None


async def tcp_ping(host: str, port: int, tries: int = PING_TRIES, timeout: float = 3.0) -> int:
    """Attempt TCP connect `tries` times; return number of successful connects."""
    success = 0
    for _ in range(tries):
        try:
            fut = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(fut, timeout=timeout)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            success += 1
        except Exception:
            await asyncio.sleep(0.15)
    return success


# ─── Pipeline ────────────────────────────────────────────────────────────
async def run_pipeline(sub_urls: list[str]) -> list[Config]:
    xray_bin = find_xray()
    log.info(f"Using Xray: {xray_bin}")

    # 1 ── Download all subscriptions
    connector = aiohttp.TCPConnector(limit=20, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        batches = await asyncio.gather(*[fetch_subscription(u, session) for u in sub_urls])

    all_uris: list[str] = []
    seen: set[str] = set()
    for batch in batches:
        for uri in batch:
            if uri not in seen:
                seen.add(uri)
                all_uris.append(uri)

    configs = [Config(raw=u, name=_parse_name(u)) for u in all_uris]
    log.info(f"Total unique configs: {len(configs)}")

    if not configs:
        return []

    # 2 ── TCP-connect filter (PING_TRIES)
    log.info("=" * 55)
    log.info("TCP ping filter — testing server connectivity")
    log.info("=" * 55)
    ping_tasks = []
    ping_map = {}
    for c in configs:
        xcfg = build_xray_config(c.raw, SOCKS_PORT_BASE)
        server = _extract_server_from_xray_cfg(xcfg) if xcfg else None
        if not server:
            ping_map[c.raw] = 0
            continue
        host, port = server
        ping_tasks.append((c, host, port))

    async def _run_ping_item(item):
        c, host, port = item
        try:
            succ = await tcp_ping(host, port)
        except Exception:
            succ = 0
        ping_map[c.raw] = succ

    await asyncio.gather(*[_run_ping_item(it) for it in ping_tasks])

    before = len(configs)
    configs = [c for c in configs if ping_map.get(c.raw, 0) >= PING_MIN_SUCCESS]
    log.info(f"✓ TCP filter: kept {len(configs)} / {before} configs (≥{PING_MIN_SUCCESS} successes)")
    if not configs:
        log.warning("No configs survived TCP ping filter")
        return []

    sem = asyncio.Semaphore(MAX_CONCURRENT)

    # 3 ── Exit-IP country check (only keep allowed countries)
    log.info("=" * 55)
    log.info("Checking exit IP country for each config")
    log.info("=" * 55)

    ports = _assign_ports(configs)

    async def _country_check(i, cfg):
        port = ports[i]
        try:
            async with XrayRunner(xray_bin, cfg, port) as runner:
                cc = await runner.get_exit_country()
                return cc
        except Exception:
            return None

    country_map = {}
    tasks = [ _country_check(i, c) for i, c in enumerate(configs) ]
    results = await asyncio.gather(*tasks)
    kept = []
    for c, cc in zip(configs, results):
        if cc and cc in ALLOWED_COUNTRIES:
            name, emoji = ALLOWED_COUNTRIES[cc]
            c.name = f"{name} {emoji}"
            kept.append(c)
        else:
            log.info(f"Dropping {c.name[:40]} — exit country: {cc}")

    configs = kept
    log.info(f"✓ Country filter: {len(configs)} configs remain")
    if not configs:
        log.warning("No configs matched allowed countries")
        return []

    # 4 ── URL tests repeated URL_TEST_ROUNDS times to compute disruption%
    log.info("=" * 55)
    log.info(f"URL tests — repeating {URL_TEST_ROUNDS} rounds")
    log.info("=" * 55)

    for c in configs:
        c.errors = 0
        c.total = 0
        c.latencies = []

    for rnd in range(URL_TEST_ROUNDS):
        log.info(f"URL test round {rnd+1}/{URL_TEST_ROUNDS}")
        ports = _assign_ports(configs)
        await asyncio.gather(*[
            test_one(xray_bin, c, ports[i], sem)
            for i, c in enumerate(configs)
        ])

    # compute disruption percentage and sort
    configs.sort(key=lambda c: (c.error_rate, c.avg_latency))
    top = configs[:TOP_N]

    log.info("=" * 55)
    log.info(f"Top {len(top)} configs (sorted by disruption then latency):")
    log.info("=" * 55)
    for i, c in enumerate(top, 1):
        log.info(f"  {i:>2}. drop%={c.error_rate*100:5.1f} latency={c.avg_latency:7.1f} ms  {c.name[:55]}")

    return top


# ─── Output ───────────────────────────────────────────────────────────────
def write_subscription(configs: list[Config], out_path: str) -> None:
    lines   = "\n".join(c.raw for c in configs)
    encoded = base64.b64encode(lines.encode()).decode()
    Path(out_path).write_text(encoded, encoding="utf-8")
    log.info(f"✅ Subscription written → {out_path}  ({len(configs)} configs)")
    # Write metadata for autoupdate and human-readable list
    meta = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "autoupdate_minutes": AUTOUPDATE_MINUTES,
        "count": len(configs),
        "items": [
            {"name": c.name, "error_rate": c.error_rate, "avg_latency_ms": c.avg_latency}
            for c in configs
        ]
    }
    meta_path = Path(out_path).with_name(out_path + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info(f"✅ Metadata written → {meta_path}")


# ─── Entry point ─────────────────────────────────────────────────────────
def load_sub_urls(config_file: str = "subscriptions.txt") -> list[str]:
    p = Path(config_file)
    if not p.exists():
        log.error(f"Subscription list not found: {config_file}")
        sys.exit(1)
    urls = [l.strip() for l in p.read_text().splitlines()
            if l.strip() and not l.startswith("#")]
    if len(urls) > 10:
        log.warning(f"More than 10 URLs ({len(urls)}); using first 10.")
        urls = urls[:10]
    return urls


async def main():
    sub_urls = load_sub_urls()
    log.info(f"Loaded {len(sub_urls)} subscription(s)")
    while True:
        try:
            top = await run_pipeline(sub_urls)
            if not top:
                log.error("No configs to write. Will retry after delay.")
            else:
                write_subscription(top, "best_configs.txt")
                # push to GitHub (reads config.env / env vars)
                try:
                    github_push.push_to_github()
                except Exception as e:
                    log.warning(f"GitHub push failed: {e}")
        except Exception as e:
            log.exception(f"Pipeline error: {e}")
        log.info(f"Sleeping {LOOP_INTERVAL_MINUTES} minutes before next run...")
        await asyncio.sleep(60 * LOOP_INTERVAL_MINUTES)


if __name__ == "__main__":
    asyncio.run(main())
