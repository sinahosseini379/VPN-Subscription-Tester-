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
