"""Parse proxy URIs (vless/vmess/trojan/ss/hysteria2) into minimal Xray configs.

Pure functions — no I/O — so they are fully unit-testable.
"""

from __future__ import annotations

import base64
import json
import urllib.parse
from dataclasses import dataclass

SUPPORTED_PREFIXES = (
    "vless://",
    "vmess://",
    "ss://",
    "shadowsocks://",
    "trojan://",
    "hy2://",
    "hysteria2://",
)
VALID_URI_PREFIXES = SUPPORTED_PREFIXES + ("tuic://",)


@dataclass
class ParsedConfig:
    uri: str
    protocol: str
    server: str
    port: int
    name: str
    outbound: dict


def strip_fragment(uri: str) -> str:
    return uri.split("#", 1)[0]


def parse_name(uri: str) -> str:
    if "#" in uri:
        return urllib.parse.unquote(uri.split("#", 1)[1])
    if uri.startswith("vmess://"):
        try:
            data = json.loads(base64.b64decode(uri[8:] + "==").decode())
            return str(data.get("ps") or data.get("add") or "vmess")
        except Exception:
            return "vmess"
    return uri[:64]


def is_supported(uri: str) -> bool:
    return any(uri.startswith(p) for p in SUPPORTED_PREFIXES)


def is_valid_uri(uri: str) -> bool:
    return any(uri.startswith(p) for p in VALID_URI_PREFIXES)


def _parse_qs(s: str) -> dict:
    return dict(urllib.parse.parse_qsl(s))


def build_stream(p: dict, allow_insecure: bool = True) -> dict:
    """Build Xray streamSettings from URI query parameters."""
    net = p.get("type") or p.get("net") or "tcp"
    security = p.get("security") or p.get("tls") or "none"
    sni = p.get("sni") or p.get("host") or ""
    host = p.get("host") or ""
    path = urllib.parse.unquote(p.get("path") or "/")
    fp = p.get("fp") or ""
    pbk = p.get("pbk") or ""
    sid = p.get("sid") or ""
    spx = urllib.parse.unquote(p.get("spx") or "")

    stream: dict = {"network": net}

    if net == "ws":
        stream["wsSettings"] = {
            "path": path,
            "headers": {"Host": host} if host else {},
        }
    elif net == "grpc":
        stream["grpcSettings"] = {
            "serviceName": p.get("serviceName") or p.get("path") or "",
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
        header_type = p.get("headerType") or "none"
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
        tls: dict = {"allowInsecure": allow_insecure}
        if sni:
            tls["serverName"] = sni
        if fp:
            tls["fingerprint"] = fp
        if p.get("alpn"):
            tls["alpn"] = p["alpn"].split(",")
        stream["tlsSettings"] = tls
    elif security == "reality":
        stream["security"] = "reality"
        stream["realitySettings"] = {
            "serverName": sni,
            "fingerprint": fp or "chrome",
            "publicKey": pbk,
            "shortId": sid,
            "spiderX": spx,
        }
    else:
        stream["security"] = "none"

    return stream


def _parse_port(raw: object) -> int | None:
    """Best-effort port parse: tolerate trailing '/', path suffix, whitespace."""
    if raw is None:
        return None
    s = str(raw).strip().split("/", 1)[0].strip()
    if not s.isdigit():
        return None
    port = int(s)
    if not 1 <= port <= 65535:
        return None
    return port


def _vless_outbound(uri: str, allow_insecure: bool = True) -> dict | None:
    u = strip_fragment(uri[len("vless://") :])
    qs = ""
    if "?" in u:
        u, qs = u.split("?", 1)
    try:
        uuid, hostport = u.rsplit("@", 1)
        host, port_str = hostport.rsplit(":", 1)
    except ValueError:
        return None
    port = _parse_port(port_str)
    if port is None:
        return None
    p = _parse_qs(qs)
    return {
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": host,
                    "port": port,
                    "users": [
                        {
                            "id": uuid,
                            "encryption": "none",
                            "flow": p.get("flow", ""),
                        }
                    ],
                }
            ]
        },
        "streamSettings": build_stream(p, allow_insecure=allow_insecure),
    }


def _vmess_outbound(uri: str, allow_insecure: bool = True) -> dict | None:
    try:
        data = json.loads(base64.b64decode(uri[8:] + "==").decode(errors="ignore"))
    except Exception:
        return None
    if "add" not in data or "port" not in data or "id" not in data:
        return None
    port = _parse_port(data.get("port"))
    if port is None:
        return None
    try:
        alter_id = int(data.get("aid", 0))
    except (TypeError, ValueError):
        alter_id = 0
    p = {
        "type": data.get("net", "tcp"),
        "security": data.get("tls", "none"),
        "host": data.get("host", data.get("add", "")),
        "path": data.get("path", "/"),
        "sni": data.get("sni", data.get("host", data.get("add", ""))),
        "fp": data.get("fp", ""),
        "alpn": data.get("alpn", ""),
    }
    return {
        "protocol": "vmess",
        "settings": {
            "vnext": [
                {
                    "address": data["add"],
                    "port": port,
                    "users": [
                        {
                            "id": data["id"],
                            "alterId": alter_id,
                            "security": data.get("scy", "auto"),
                        }
                    ],
                }
            ]
        },
        "streamSettings": build_stream(p, allow_insecure=allow_insecure),
    }


def _trojan_outbound(uri: str, allow_insecure: bool = True) -> dict | None:
    u = strip_fragment(uri[len("trojan://") :])
    qs = ""
    if "?" in u:
        u, qs = u.split("?", 1)
    try:
        password, hostport = u.rsplit("@", 1)
        host, port_str = hostport.rsplit(":", 1)
    except ValueError:
        return None
    port = _parse_port(port_str)
    if port is None:
        return None
    p = _parse_qs(qs)
    p.setdefault("security", "tls")
    return {
        "protocol": "trojan",
        "settings": {
            "servers": [
                {
                    "address": host,
                    "port": port,
                    "password": password,
                }
            ]
        },
        "streamSettings": build_stream(p, allow_insecure=allow_insecure),
    }


def _hysteria2_outbound(uri: str, allow_insecure: bool = True) -> dict | None:
    prefix = "hysteria2://" if uri.startswith("hysteria2://") else "hy2://"
    u = strip_fragment(uri[len(prefix) :])
    qs = ""
    if "?" in u:
        u, qs = u.split("?", 1)
    try:
        password, hostport = u.rsplit("@", 1)
        host, port_str = hostport.rsplit(":", 1)
    except ValueError:
        return None
    if not host or not password:
        return None
    port = _parse_port(port_str)
    if port is None:
        return None

    p = _parse_qs(qs)
    password = urllib.parse.unquote(password)

    insecure = allow_insecure
    raw_ins = p.get("insecure") or p.get("allowInsecure")
    if raw_ins is not None:
        insecure = raw_ins.strip().lower() in ("1", "true", "yes", "on")

    obfs = (p.get("obfs") or "").strip()
    if obfs.lower() in ("", "none", "plain"):
        obfs = ""
    obfs_pw = p.get("obfs-password") or p.get("obfspassword") or ""

    tls: dict = {
        "serverName": p.get("sni") or p.get("peer") or host,
        "allowInsecure": insecure,
    }
    if p.get("fp"):
        tls["fingerprint"] = p["fp"]

    server = {"address": host, "port": port, "password": password, "tlsSettings": tls}
    if obfs:
        server["obfs"] = obfs
        server["obfs-password"] = obfs_pw

    return {"protocol": "hysteria2", "settings": {"servers": [server]}}


def _ss_outbound(uri: str) -> dict | None:
    prefix = "shadowsocks://" if uri.startswith("shadowsocks://") else "ss://"
    u = strip_fragment(uri[len(prefix) :])
    qs = ""
    if "?" in u:
        u, qs = u.split("?", 1)

    method, password, host, port_str = "", "", "", ""
    if "@" in u:
        userinfo, hostport = u.rsplit("@", 1)
        try:
            userinfo = base64.b64decode(userinfo + "==").decode(errors="ignore")
        except Exception:
            userinfo = urllib.parse.unquote(userinfo)
        if ":" not in userinfo:
            return None
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

    if not all([method, password, host, port_str]):
        return None
    port = _parse_port(port_str)
    if port is None:
        return None

    return {
        "protocol": "shadowsocks",
        "settings": {
            "servers": [
                {
                    "address": host,
                    "port": port,
                    "method": method,
                    "password": password,
                }
            ]
        },
        "streamSettings": {"network": "tcp"},
    }


def parse_uri(uri: str, allow_insecure: bool = True) -> ParsedConfig | None:
    """Parse a single URI. Returns ParsedConfig or None if unsupported/malformed."""
    if not is_supported(uri):
        return None

    if uri.startswith("vless://"):
        out = _vless_outbound(uri, allow_insecure=allow_insecure)
        protocol = "vless"
    elif uri.startswith("vmess://"):
        out = _vmess_outbound(uri, allow_insecure=allow_insecure)
        protocol = "vmess"
    elif uri.startswith("trojan://"):
        out = _trojan_outbound(uri, allow_insecure=allow_insecure)
        protocol = "trojan"
    elif uri.startswith(("hy2://", "hysteria2://")):
        out = _hysteria2_outbound(uri, allow_insecure=allow_insecure)
        protocol = "hysteria2"
    else:
        out = _ss_outbound(uri)
        protocol = "shadowsocks"

    if out is None:
        return None

    server, port = _server_from_outbound(out)
    if not server or not port:
        return None

    return ParsedConfig(
        uri=uri,
        protocol=protocol,
        server=server,
        port=port,
        name=parse_name(uri),
        outbound=out,
    )


def _server_from_outbound(outbound: dict) -> tuple[str, int]:
    proto = outbound.get("protocol", "")
    sets = outbound.get("settings", {})
    try:
        if proto in ("vless", "vmess"):
            vnext = sets.get("vnext", [])
            if vnext:
                return vnext[0].get("address", ""), int(vnext[0].get("port", 0))
        if proto in ("shadowsocks", "trojan", "hysteria2"):
            sv = sets.get("servers", [])
            if sv:
                return sv[0].get("address", ""), int(sv[0].get("port", 0))
    except (TypeError, ValueError):
        return "", 0
    return "", 0


def wrap_xray_config(outbound: dict, socks_port: int) -> dict:
    """Wrap an outbound dict into a minimal runnable Xray config."""
    outbound = dict(outbound)
    outbound["tag"] = "proxy"
    inbounds = [
        {
            "tag": "socks-in",
            "port": socks_port,
            "listen": "127.0.0.1",
            "protocol": "socks",
            "settings": {"udp": False},
            "sniffing": {"enabled": False},
        }
    ]
    return {
        "log": {"loglevel": "none"},
        "inbounds": inbounds,
        "outbounds": [
            outbound,
            {"tag": "direct", "protocol": "freedom"},
            {"tag": "block", "protocol": "blackhole"},
        ],
        "routing": {
            "rules": [
                {
                    "type": "field",
                    "network": "tcp,udp",
                    "outboundTag": "proxy",
                }
            ]
        },
        "policy": {
            "levels": {"0": {"handshake": 4, "connIdle": 30}},
            "system": {"statsOutboundUplink": False, "statsOutboundDownlink": False},
        },
    }


def build_xray_config(uri: str, socks_port: int, allow_insecure: bool = True) -> dict | None:
    """High-level helper: URI + socks port -> full runnable Xray JSON dict."""
    parsed = parse_uri(uri, allow_insecure=allow_insecure)
    if parsed is None:
        return None
    return wrap_xray_config(parsed.outbound, socks_port=socks_port)


# -- alternate cores (sing-box / hysteria) -------------------------------


def set_fragment(uri: str, name: str) -> str:
    """Replace (or add) the #fragment of a URI with a URL-encoded node name."""
    base = uri.split("#", 1)[0]
    return f"{base}#{urllib.parse.quote(name)}"


def _singbox_tls(stream: dict, server: str, port: int, allow_insecure: bool) -> dict:
    security = stream.get("security")
    if security not in ("tls", "reality"):
        return {}
    tls: dict = {"enabled": True}
    if security == "tls":
        ts = stream.get("tlsSettings", {})
        tls["server_name"] = ts.get("serverName", "")
        tls["insecure"] = bool(ts.get("allowInsecure", allow_insecure))
        if ts.get("alpn"):
            tls["alpn"] = ts["alpn"]
        if ts.get("fingerprint"):
            tls["utls"] = {"enabled": True, "fingerprint": ts["fingerprint"]}
    else:
        rs = stream.get("realitySettings", {})
        sni = rs.get("serverName", "")
        tls["server_name"] = sni
        tls["utls"] = {"enabled": True, "fingerprint": rs.get("fingerprint") or "chrome"}
        tls["reality"] = {
            "enabled": True,
            "public_key": rs.get("publicKey", ""),
            "short_id": rs.get("shortId", ""),
            "handshake": {"server": sni, "port": port},
        }
    return tls


def _singbox_transport(stream: dict) -> dict | None:
    net = stream.get("network")
    if net == "ws":
        ws = stream.get("wsSettings", {})
        tr: dict = {"type": "ws", "path": ws.get("path", "/")}
        host = (ws.get("headers") or {}).get("Host", "")
        if host:
            tr["headers"] = {"Host": host}
        return tr
    if net == "grpc":
        return {
            "type": "grpc",
            "service_name": (stream.get("grpcSettings") or {}).get("serviceName", ""),
        }
    if net == "h2":
        h = stream.get("httpSettings", {})
        return {"type": "http", "host": h.get("host", []), "path": h.get("path", "/")}
    if net == "httpupgrade":
        h = stream.get("httpupgradeSettings", {})
        return {"type": "httpupgrade", "host": h.get("host", ""), "path": h.get("path", "/")}
    if net == "splithttp":
        return {
            "type": "splithttp",
            "path": (stream.get("splithttpSettings") or {}).get("path", "/"),
        }
    if net == "tcp":
        header = (stream.get("tcpSettings") or {}).get("header") or {}
        if header.get("type") == "http":
            req = header.get("request", {})
            hosts = (req.get("headers") or {}).get("Host", [""])
            paths = req.get("path", [""])
            return {
                "type": "http",
                "host": hosts if isinstance(hosts, list) else [hosts],
                "path": paths if isinstance(paths, list) else [paths],
            }
    return None


def to_singbox_outbound(outbound: dict, allow_insecure: bool = True) -> dict | None:
    """Convert an Xray-format outbound dict into a sing-box outbound dict."""
    proto = outbound.get("protocol")
    sets = outbound.get("settings", {})
    stream = outbound.get("streamSettings", {})
    try:
        if proto in ("vless", "vmess"):
            v = sets["vnext"][0]
            user = v["users"][0]
            ob: dict = {
                "type": proto,
                "tag": "proxy",
                "server": v["address"],
                "server_port": v["port"],
            }
            ob["uuid"] = user["id"]
            if proto == "vless":
                if user.get("flow"):
                    ob["flow"] = user["flow"]
            else:
                ob["security"] = user.get("security", "auto")
                ob["alter_id"] = int(user.get("alterId", 0))
            tls = _singbox_tls(stream, v["address"], v["port"], allow_insecure)
            if tls:
                ob["tls"] = tls
            tr = _singbox_transport(stream)
            if tr:
                ob["transport"] = tr
            return ob
        if proto in ("trojan", "shadowsocks", "hysteria2"):
            s = sets["servers"][0]
            ob = {"type": proto, "tag": "proxy", "server": s["address"], "server_port": s["port"]}
            if proto == "trojan":
                ob["password"] = s["password"]
                tls = _singbox_tls(stream, s["address"], s["port"], allow_insecure)
                if tls:
                    ob["tls"] = tls
                tr = _singbox_transport(stream)
                if tr:
                    ob["transport"] = tr
            elif proto == "shadowsocks":
                ob["method"] = s["method"]
                ob["password"] = s["password"]
            else:  # hysteria2
                ts = s.get("tlsSettings", {})
                tls = {
                    "enabled": True,
                    "server_name": ts.get("serverName", s["address"]),
                    "insecure": bool(ts.get("allowInsecure", allow_insecure)),
                }
                if ts.get("fingerprint"):
                    tls["utls"] = {"enabled": True, "fingerprint": ts["fingerprint"]}
                ob["tls"] = tls
                if s.get("obfs"):
                    ob["obfs"] = {"type": s["obfs"], "password": s.get("obfs-password", "")}
            return ob
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    return None


def build_singbox_config(uri: str, socks_port: int, allow_insecure: bool = True) -> dict | None:
    """URI + socks port -> full runnable sing-box JSON dict (fallback core)."""
    parsed = parse_uri(uri, allow_insecure=allow_insecure)
    if parsed is None:
        return None
    outbound = to_singbox_outbound(parsed.outbound, allow_insecure=allow_insecure)
    if outbound is None:
        return None
    return {
        "log": {"level": "error"},
        "inbounds": [
            {
                "type": "socks",
                "tag": "socks-in",
                "listen": "127.0.0.1",
                "listen_port": socks_port,
            }
        ],
        "outbounds": [
            outbound,
            {"type": "direct", "tag": "direct"},
            {"type": "block", "tag": "block"},
        ],
        "route": {"rules": [], "final": "proxy"},
    }


def build_hysteria_client_config(
    uri: str, socks_port: int, allow_insecure: bool = True
) -> str | None:
    """URI + socks port -> hysteria (Hysteria2) client YAML string."""
    parsed = parse_uri(uri, allow_insecure=allow_insecure)
    if parsed is None or parsed.protocol != "hysteria2":
        return None
    s = parsed.outbound["settings"]["servers"][0]
    ts = s.get("tlsSettings", {})
    cfg = {
        "server": f"{s['address']}:{s['port']}",
        "auth": s["password"],
        "tls": {
            "sni": ts.get("serverName", s["address"]),
            "insecure": bool(ts.get("allowInsecure", allow_insecure)),
        },
        "socks5": {"listen": f"127.0.0.1:{socks_port}"},
    }
    if ts.get("fingerprint"):
        cfg["tls"]["fingerprint"] = ts["fingerprint"]
    if s.get("obfs"):
        cfg["obfs"] = {"type": s["obfs"], "salamander": {"password": s.get("obfs-password", "")}}
    import yaml

    return yaml.safe_dump(cfg, sort_keys=False)


# -- stealth / ISP-resilience scoring ------------------------------------
#
# Iranian ISPs use different DPI engines with varying capabilities.  Configs
# that look like normal HTTPS browsing survive across all operators; configs
# using unencrypted, unusual, or easily fingerprinted protocols get blocked
# on some ISPs even though they work fine on others.
#
# The score is a weighted sum of independent signals, each normalised to
# [0, 1].  A combined score of 1.0 means "very hard to detect/block"; 0.0
# means "trivially blocked by basic filtering".
#
# Weights are tuned based on real-world observations of Iranian ISP blocking
# behaviour as of 2024-2025 (MCI, Irancell, Rightel, Shatel, Samantel, …).

# (signal_name, weight)
_STEALTH_WEIGHTS = {
    "security":    0.35,  # TLS/Reality vs none — biggest single factor
    "transport":   0.25,  # ws/httpupgrade vs grpc/tcp-raw
    "fingerprint": 0.15,  # uTLS fingerprint presence (anti-DPI)
    "port":        0.10,  # 443 is safest; exotic ports draw attention
    "protocol":    0.15,  # vless > trojan > vmess > ss (detection difficulty)
}

_SECURITY_SCORES: dict[str, float] = {
    "reality": 1.0,   # looks like genuine TLS to a real site — undetectable
    "tls":     0.7,   # standard TLS — good but can be fingerprinted
    "none":    0.0,   # plaintext — instantly detectable
}

_TRANSPORT_SCORES: dict[str, float] = {
    "ws":          0.9,   # WebSocket over TLS — looks like normal web traffic
    "httpupgrade": 0.9,   # HTTP Upgrade — same profile as WebSocket
    "splithttp":   0.85,  # newer, less fingerprinted
    "h2":          0.7,   # HTTP/2 — good but less common for browsing
    "grpc":        0.4,   # gRPC — unusual pattern, some ISPs block it
    "tcp":         0.3,   # raw TCP — easy to fingerprint unless camouflaged
}

_PROTOCOL_SCORES: dict[str, float] = {
    "vless":       1.0,   # minimal overhead, hard to fingerprint
    "trojan":      0.8,   # looks like TLS to a web server
    "hysteria2":   0.7,   # QUIC-based — works on some ISPs, blocked on others
    "vmess":       0.5,   # detectable header pattern (even with TLS)
    "shadowsocks": 0.3,   # well-known fingerprint, often blocked
}

# Good uTLS fingerprints that make TLS look like real browser traffic.
_GOOD_FINGERPRINTS = frozenset({
    "chrome", "firefox", "safari", "edge", "ios", "android",
    "randomized", "random", "hellorandomizedalpn",
    "hellorandomizednoalpn", "hellofirefox_auto",
    "hellochrome_auto",
})


def _port_score(port: int) -> float:
    """Score a port by how likely it is to pass ISP filtering."""
    if port == 443:
        return 1.0
    if port == 8443:
        return 0.9
    if port in (2053, 2083, 2087, 2096):  # Cloudflare HTTPS ports
        return 0.85
    if port == 80:
        return 0.5   # HTTP — no encryption expected, stands out
    if port in (8080, 8880, 2052, 2082, 2086, 2095):  # Cloudflare HTTP ports
        return 0.4
    # Anything else: high ports are less suspicious than low ones
    if port > 1024:
        return 0.3
    return 0.1


def _fingerprint_score(fp: str) -> float:
    """Score a TLS fingerprint string."""
    if not fp:
        return 0.0  # no fingerprint = no uTLS = easily fingerprinted
    return 1.0 if fp.lower() in _GOOD_FINGERPRINTS else 0.5


def extract_stealth_info(parsed: ParsedConfig) -> dict:
    """Extract stealth-relevant metadata from a parsed config.

    Returns a dict with keys: transport, security, fingerprint, stealth_score.
    """
    outbound = parsed.outbound
    protocol = parsed.protocol
    stream = outbound.get("streamSettings", {})

    transport = stream.get("network", "tcp")
    security = stream.get("security", "none")
    port = parsed.port

    # Extract fingerprint from TLS or Reality settings
    fingerprint = ""
    if security == "tls":
        fingerprint = (stream.get("tlsSettings") or {}).get("fingerprint", "")
    elif security == "reality":
        fingerprint = (stream.get("realitySettings") or {}).get("fingerprint", "")

    # Hysteria2 is a special case — it's always TLS + QUIC, no stream settings
    if protocol == "hysteria2":
        transport = "quic"
        security = "tls"
        servers = outbound.get("settings", {}).get("servers", [])
        if servers:
            fingerprint = (servers[0].get("tlsSettings") or {}).get("fingerprint", "")

    # Special case: TCP with HTTP camouflage header
    if transport == "tcp":
        tcp_settings = stream.get("tcpSettings", {})
        header = tcp_settings.get("header", {})
        if header.get("type") == "http":
            transport = "tcp-http"  # camouflaged TCP — slightly better

    # Calculate the composite score
    sec_score = _SECURITY_SCORES.get(security, 0.0)
    trans_score = _TRANSPORT_SCORES.get(transport, 0.3)
    if transport == "tcp-http":
        trans_score = 0.45  # better than raw TCP but still detectable
    if transport == "quic":
        trans_score = 0.6   # QUIC is promising but blocked by some ISPs
    fp_score = _fingerprint_score(fingerprint)
    p_score = _port_score(port)
    proto_score = _PROTOCOL_SCORES.get(protocol, 0.3)

    # Bonus: Reality on port 443 with a good fingerprint is basically
    # indistinguishable from real HTTPS — give it a bump.
    bonus = 0.0
    if security == "reality" and port == 443 and fingerprint:
        bonus = 0.05

    stealth_score = (
        _STEALTH_WEIGHTS["security"] * sec_score
        + _STEALTH_WEIGHTS["transport"] * trans_score
        + _STEALTH_WEIGHTS["fingerprint"] * fp_score
        + _STEALTH_WEIGHTS["port"] * p_score
        + _STEALTH_WEIGHTS["protocol"] * proto_score
        + bonus
    )
    # Clamp to [0, 1]
    stealth_score = min(1.0, max(0.0, stealth_score))

    return {
        "transport": transport,
        "security": security,
        "fingerprint": fingerprint,
        "stealth_score": round(stealth_score, 3),
    }
