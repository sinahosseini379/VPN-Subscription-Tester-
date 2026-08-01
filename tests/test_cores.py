from __future__ import annotations

import asyncio
import re
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

from vpn_tester.config import Settings
from vpn_tester.cores import (
    CORE_DEFS,
    _extract_member,
    _hysteria_asset,
    _installed_version,
    _norm_version,
    _pick_asset,
    _singbox_asset,
    _xray_asset,
    ensure_cores,
)


def test_norm_version():
    assert _norm_version("v1.2.3") == "1.2.3"
    assert _norm_version("V2.0.0") == "2.0.0"
    assert _norm_version(" 1.2.3 ") == "1.2.3"


def test_asset_matchers():
    assert _xray_asset("Xray-linux-64.zip")
    assert not _xray_asset("Xray-linux-arm64.zip")
    assert _singbox_asset("sing-box-1.9.0-linux-amd64.tar.gz")
    assert not _singbox_asset("sing-box-1.9.0-linux-arm64.tar.gz")
    assert _hysteria_asset("hysteria-linux-amd64")
    assert not _hysteria_asset("hysteria-linux-arm64")


def test_pick_asset():
    release = {"assets": [{"name": "Xray-linux-64.zip", "browser_download_url": "https://x/y"}]}
    assert _pick_asset(release, CORE_DEFS[0]) == "https://x/y"
    assert _pick_asset({"assets": [{"name": "other"}]}, CORE_DEFS[0]) is None


def _fake_core(binary_path: Path):
    return SimpleNamespace(
        name="fake",
        settings_field="xray_bin",
        version_cmd=[sys.executable, str(binary_path)],
        version_re=re.compile(r"Xray\s+([0-9A-Za-z._-]+)"),
    )


def test_installed_version_parses(tmp_path, monkeypatch):
    from subprocess import CompletedProcess

    binary = tmp_path / "xray"
    binary.write_bytes(b"\x7fELF")
    fake = _fake_core(binary)
    monkeypatch.setattr(
        "vpn_tester.cores.subprocess.run",
        lambda *a, **k: CompletedProcess(a, 0, stdout="Xray v1.2.3\n"),
    )
    assert _installed_version(binary, fake) == "1.2.3"


def test_installed_version_missing_file(tmp_path):
    assert _installed_version(tmp_path / "nope", _fake_core(tmp_path / "x")) == ""


def test_installed_version_nonzero_exit(tmp_path, monkeypatch):
    from subprocess import CompletedProcess

    fake = _fake_core(tmp_path / "x")
    monkeypatch.setattr(
        "vpn_tester.cores.subprocess.run",
        lambda *a, **k: CompletedProcess(a, 1, stdout="boom"),
    )
    assert _installed_version(tmp_path / "x", fake) == ""


def test_extract_member_zip(tmp_path):
    archive = tmp_path / "core.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("dir/other.txt", "nope")
        zf.writestr("core-dir/xray", "BINPAYLOAD")
    dest = tmp_path / "xray"
    _extract_member(archive, "xray", dest, "zip")
    assert dest.read_text(encoding="utf-8") == "BINPAYLOAD"


def test_ensure_cores_explicit_paths_wins(tmp_path):
    s = Settings(
        auto_update_cores=False,
        cores_dir=str(tmp_path / "cores"),
        xray_bin="/opt/xray",
        sing_box_bin="/opt/sing-box",
        hysteria_bin="/opt/hysteria",
    )
    cores = asyncio.run(ensure_cores(s))
    assert cores.xray == "/opt/xray"
    assert cores.sing_box == "/opt/sing-box"
    assert cores.hysteria == "/opt/hysteria"


def test_ensure_cores_auto_update_uses_existing_binary(tmp_path, monkeypatch):
    """When a binary already sits in cores_dir at the latest version, no network
    call is needed and the installed binary is resolved."""
    from vpn_tester import cores as cores_mod

    binary = tmp_path / "cores" / "xray"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"\x7fELF")
    monkeypatch.setattr(
        cores_mod,
        "_installed_version",
        lambda p, c: "9.9.9" if str(p) == str(binary) else "",
    )

    async def _latest(*_a, **_k):
        return {"tag_name": "v9.9.9", "assets": []}

    monkeypatch.setattr(cores_mod, "_latest_release", _latest)
    s = Settings(auto_update_cores=True, cores_dir=str(tmp_path / "cores"), xray_bin="")
    cores = asyncio.run(ensure_cores(s))
    assert cores.xray == str(binary)
