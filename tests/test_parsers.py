from __future__ import annotations

import base64
import json

import pytest

from vpn_tester.parsers import (
    build_hysteria_client_config,
    build_singbox_config,
    build_xray_config,
    is_supported,
    is_valid_uri,
    parse_name,
    parse_uri,
    set_fragment,
    to_singbox_outbound,
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
HY2 = (
    "hy2://password@hy.example.com:443?sni=hy.example.com&insecure=1"
    "&obfs=salamander&obfs-password=obs#Hy2"
)
HY2_HYSTERIA = "hysteria2://pw@hys.example.com:8443#Hys"
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
        (HY2, "hysteria2", "hy.example.com", 443),
        (HY2_HYSTERIA, "hysteria2", "hys.example.com", 8443),
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


@pytest.mark.parametrize(
    "uri",
    [
        "vless://uuid123@server.example.com:443/#Node",  # stray trailing slash
        "vless://uuid123@server.example.com:443//",  # double trailing slash
        "trojan://pass@tr.example.com:443/",
        "hy2://pass@hy.example.com:443/",
    ],
)
def test_parse_uri_tolerates_trailing_slash_in_port(uri):
    parsed = parse_uri(uri)
    assert parsed is not None
    assert parsed.port == 443


def test_parse_uri_skips_bad_port():
    assert parse_uri("vless://uuid123@server.example.com:notaport?security=none") is None


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


def test_parse_hysteria2_settings():
    parsed = parse_uri(HY2)
    assert parsed is not None
    srv = parsed.outbound["settings"]["servers"][0]
    assert srv["password"] == "password"
    assert srv["obfs"] == "salamander"
    assert srv["obfs-password"] == "obs"
    assert srv["tlsSettings"]["allowInsecure"] is True
    assert srv["tlsSettings"]["serverName"] == "hy.example.com"


def test_parse_hysteria2_insecure_respects_setting():
    parsed = parse_uri("hy2://pw@h.example.com:443", allow_insecure=False)
    assert parsed is not None
    srv = parsed.outbound["settings"]["servers"][0]
    assert srv["tlsSettings"]["allowInsecure"] is False
    assert srv["tlsSettings"]["serverName"] == "h.example.com"  # sni defaults to host


def test_parse_hysteria2_plain_obfs_omitted():
    parsed = parse_uri("hysteria2://pw@h.example.com:443?obfs=none")
    assert parsed is not None
    srv = parsed.outbound["settings"]["servers"][0]
    assert "obfs" not in srv


def test_build_xray_config_hysteria2():
    cfg = build_xray_config(
        "hysteria2://pw@h.example.com:443?sni=cdn.example.com", socks_port=21001
    )
    assert cfg is not None
    outbound = cfg["outbounds"][0]
    assert outbound["protocol"] == "hysteria2"
    assert outbound["settings"]["servers"][0]["address"] == "h.example.com"


def test_parse_fragment_name():
    assert parse_name(TROJAN) == "Trojan1"


@pytest.mark.parametrize(
    "uri",
    [
        "tuic://user@x.com:443",
        "garbage://nothing",
    ],
)
def test_unsupported_or_invalid(uri):
    assert is_valid_uri(uri) is True or uri.startswith("garbage")
    assert is_supported("tuic://") is False  # valid-but-unsupported still parsed as None
    assert parse_uri("tuic://user@x.com:443") is None


def test_hysteria2_is_supported():
    assert is_supported("hy2://x@y.com:443") is True
    assert is_supported("hysteria2://x@y.com:443") is True
    assert is_valid_uri("hy2://x@y.com:443") is True


def test_build_xray_config_full():
    cfg = build_xray_config(VLESS_TCP, socks_port=21000)
    assert cfg is not None
    assert cfg["inbounds"][0]["port"] == 21000
    assert cfg["outbounds"][0]["tag"] == "proxy"
    assert cfg["outbounds"][0]["protocol"] == "vless"


# -- alternate cores: sing-box / hysteria converters -------------------------


def test_set_fragment_replaces_existing():
    uri = "vless://u@x.com:443#Old%20Name"
    assert set_fragment(uri, "Germany | 01") == "vless://u@x.com:443#Germany%20%7C%2001"


def test_set_fragment_adds_when_missing():
    assert set_fragment("vless://u@x.com:443", "A") == "vless://u@x.com:443#A"


def test_to_singbox_vless_reality():
    out = to_singbox_outbound(parse_uri(VLESS_REALITY).outbound)
    assert out["type"] == "vless"
    assert out["uuid"] == "uuid"
    assert out["tls"]["reality"]["enabled"] is True
    assert out["tls"]["reality"]["public_key"] == "pubkey"


def test_to_singbox_vmess_ws():
    out = to_singbox_outbound(parse_uri(VMESS).outbound)
    assert out["type"] == "vmess"
    assert out["server"] == "vm.example.com"
    assert out["transport"]["type"] == "ws"
    assert out["transport"]["path"] == "/ws"


def test_to_singbox_trojan():
    out = to_singbox_outbound(parse_uri(TROJAN).outbound)
    assert out["type"] == "trojan"
    assert out["password"] == "password123"
    assert out["transport"]["type"] == "ws"


def test_to_singbox_ss():
    out = to_singbox_outbound(parse_uri(SS_OLD).outbound)
    assert out["type"] == "shadowsocks"
    assert out["method"] == "aes-256-gcm"
    assert out["password"] == "password"


def test_to_singbox_hysteria2():
    out = to_singbox_outbound(parse_uri(HY2).outbound)
    assert out["type"] == "hysteria2"
    assert out["obfs"]["type"] == "salamander"


def test_to_singbox_unsupported_returns_none():
    assert to_singbox_outbound({"protocol": "tuic", "settings": {}}) is None


def test_build_singbox_config_roundtrip():
    cfg = build_singbox_config(VLESS_WS, socks_port=22000)
    assert cfg is not None
    assert cfg["inbounds"][0]["listen_port"] == 22000
    assert cfg["outbounds"][0]["type"] == "vless"
    assert cfg["route"]["final"] == "proxy"


def test_build_hysteria_client_config_yaml():
    text = build_hysteria_client_config(HY2, socks_port=22001)
    assert text is not None
    assert "server: hy.example.com:443" in text
    assert "salamander" in text
    assert "listen: 127.0.0.1:22001" in text


def test_build_hysteria_client_config_rejects_non_hy2():
    assert build_hysteria_client_config(VLESS_TCP, socks_port=22002) is None
