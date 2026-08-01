from __future__ import annotations

import base64

from vpn_tester.subscription import (
    clash_proxy_to_uri,
    decode_subscription,
    extract_json_uris,
    singbox_outbound_to_uri,
)


def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def test_decode_base64_list():
    payload = _b64("vless://a@x.com:443#one\nvmess://bad\nss://u:p@s.com:443")
    uris = decode_subscription(payload)
    assert "vless://a@x.com:443#one" in uris
    # invalid vmess base64 line gets filtered by validity check
    assert any(u.startswith("ss://") for u in uris)


def test_decode_base64_requires_prefix():
    # base64 of plain text that is not a uri list should fall through
    text = "hello world\nthis is not base64-encoded subscriptions"
    # Ensure it's treated as plain list
    uris = decode_subscription(text)
    assert uris == []  # none are valid URIs


def test_decode_plain_list():
    text = "\n".join(
        [
            "# comment",
            "vless://a@x.com:443#one",
            "",
            "trojan://pw@t.com:443#two",
        ]
    )
    uris = decode_subscription(text)
    assert uris == ["vless://a@x.com:443#one", "trojan://pw@t.com:443#two"]


def test_decode_singbox_json():
    obj = {
        "outbounds": [
            {
                "type": "vless",
                "tag": "us1",
                "server": "s.example.com",
                "server_port": 443,
                "uuid": "uu-id",
            },
            {
                "type": "shadowsocks",
                "tag": "ss1",
                "server": "ss.example.com",
                "server_port": 8388,
                "method": "aes-256-gcm",
                "password": "p",
            },
        ]
    }
    uris = extract_json_uris(obj)
    assert len(uris) == 2
    assert uris[0].startswith("vless://uu-id@s.example.com:443")


def test_decode_clash_json():
    obj = {
        "proxies": [
            {
                "type": "trojan",
                "name": "tr",
                "server": "t.example.com",
                "port": 443,
                "password": "pass",
            },
            {
                "type": "ss",
                "name": "s1",
                "server": "s.example.com",
                "port": 443,
                "cipher": "chacha20-ietf-poly1305",
                "password": "pp",
            },
        ]
    }
    uris = extract_json_uris(obj)
    assert len(uris) == 2
    assert uris[0].startswith("trojan://pass@t.example.com:443")


def test_decode_nested_json():
    obj = [
        {
            "proxies": [
                {
                    "type": "ss",
                    "name": "n",
                    "server": "n.example.com",
                    "port": 1,
                    "cipher": "aes-128-gcm",
                    "password": "x",
                }
            ]
        }
    ]
    assert extract_json_uris(obj)


def test_singbox_outbound_requires_server():
    assert singbox_outbound_to_uri({"type": "vless", "tag": "x"}) is None


def test_clash_uri_fragment_encoding():
    uri = clash_proxy_to_uri(
        {
            "type": "trojan",
            "name": "My Node",
            "server": "t.example.com",
            "port": 443,
            "password": "pw",
        }
    )
    assert uri is not None
    assert "%20" in uri  # space encoded
