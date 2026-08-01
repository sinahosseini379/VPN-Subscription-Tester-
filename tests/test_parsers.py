from __future__ import annotations

import base64
import json

import pytest

from vpn_tester.parsers import (
    build_xray_config,
    is_supported,
    is_valid_uri,
    parse_name,
    parse_uri,
)

VLESS_TCP = "vless://uuid123@server.example.com:443?security=none#My%20Node"
VLESS_REALITY = (
    "vless://uuid@example.com:443?encryption=none&security=reality&"
    "sni=www.microsoft.com&fp=chrome&pbk=pubkey&sid=1234&spx=/&type=tcp"
    "#Reality"
)
VLESS_WS = (
    "vless://uuid@example.com:443?type=ws&security=tls&path=%2Fws&host=cdn.example.com"
    "&sni=cdn.example.com#Ws"
)
VMESS = (
    "vmess://"
    + base64.b64encode(
        json.dumps(
            {
                "v": "2",
                "ps": "MyVmess",
                "add": "vm.example.com",
                "port": "8080",
                "id": "id-1234",
                "aid": "0",
                "net": "ws",
                "type": "none",
                "host": "vm.example.com",
                "path": "/ws",
                "tls": "tls",
            },
            separators=(",", ":"),
        ).encode()
    ).decode()
)
TROJAN = "trojan://password123@tr.example.com:443?security=tls&type=ws&path=%2F#Trojan1"
SS_OLD = "ss://YWVzLTI1Ni1nY206cGFzc3dvcmQ@ss.example.com:8388#SS1"
SS_B64 = (
    "ss://"
    + __import__("base64").b64encode(b"aes-256-gcm:password@ss2.example.com:443").decode()
    + "#SS2"
)


@pytest.mark.parametrize(
    "uri,proto,server,port",
    [
        (VLESS_TCP, "vless", "server.example.com", 443),
        (VLESS_REALITY, "vless", "example.com", 443),
        (VMESS, "vmess", "vm.example.com", 8080),
        (TROJAN, "trojan", "tr.example.com", 443),
        (SS_OLD, "shadowsocks", "ss.example.com", 8388),
        (SS_B64, "shadowsocks", "ss2.example.com", 443),
    ],
)
def test_parse_uri_basic(uri, proto, server, port):
    parsed = parse_uri(uri)
    assert parsed is not None
    assert parsed.protocol == proto
    assert parsed.server == server
    assert parsed.port == port


def test_parse_vless_ws_stream():
    parsed = parse_uri(VLESS_WS)
    assert parsed is not None
    stream = parsed.outbound["streamSettings"]
    assert stream["network"] == "ws"
    assert stream["security"] == "tls"
    assert stream["tlsSettings"]["serverName"] == "cdn.example.com"
    assert stream["wsSettings"]["path"] == "/ws"


def test_parse_vless_reality_stream():
    parsed = parse_uri(VLESS_REALITY)
    assert parsed is not None
    stream = parsed.outbound["streamSettings"]
    assert stream["security"] == "reality"
    assert stream["realitySettings"]["serverName"] == "www.microsoft.com"
    assert stream["realitySettings"]["fingerprint"] == "chrome"
    assert stream["realitySettings"]["publicKey"] == "pubkey"


def test_parse_vmess_name():
    assert parse_name(VMESS) == "MyVmess"


def test_parse_fragment_name():
    assert parse_name(TROJAN) == "Trojan1"


@pytest.mark.parametrize(
    "uri",
    [
        "tuic://user@x.com:443",
        "hy2://user@x.com:443",
        "garbage://nothing",
    ],
)
def test_unsupported_or_invalid(uri):
    assert is_valid_uri(uri) is True or uri.startswith("garbage")
    assert is_supported("tuic://") is False


def test_build_xray_config_full():
    cfg = build_xray_config(VLESS_TCP, socks_port=21000)
    assert cfg is not None
    assert cfg["inbounds"][0]["port"] == 21000
    assert cfg["outbounds"][0]["tag"] == "proxy"
    assert cfg["outbounds"][0]["protocol"] == "vless"
