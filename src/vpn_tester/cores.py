"""Managed proxy cores: Xray, sing-box and Hysteria2.

Downloads the latest release of each core from its official GitHub repo into
``settings.cores_dir`` and re-checks for updates on every run. Version is
verified by running the binary, so a bad download is never left in place.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import shutil
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import aiohttp

from .config import Settings

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
DOWNLOAD_TIMEOUT = aiohttp.ClientTimeout(total=600)
API_HEADERS = {"Accept": "application/vnd.github+json"}


@dataclass
class Cores:
    """Resolved paths to the three core binaries."""

    xray: str = ""
    sing_box: str = ""
    hysteria: str = ""

    def present(self) -> list[str]:
        return [p for p in (self.xray, self.sing_box, self.hysteria) if p]


def _norm_version(raw: str) -> str:
    return raw.strip().lstrip("vV")


@dataclass
class CoreDef:
    name: str
    settings_field: str  # Settings attribute (env override)
    cores_field: str  # Cores dataclass attribute
    owner: str
    repo: str
    version_cmd: list[str]
    version_re: re.Pattern
    archive: str  # "zip" | "tar" | "none"
    binary_name: str
    asset_match: callable  # (name: str) -> bool


def _xray_asset(name: str) -> bool:
    return name == "Xray-linux-64.zip"


def _singbox_asset(name: str) -> bool:
    return name.startswith("sing-box-") and "-linux-amd64" in name and name.endswith(".tar.gz")


def _hysteria_asset(name: str) -> bool:
    return name == "hysteria-linux-amd64"


CORE_DEFS: list[CoreDef] = [
    CoreDef(
        name="xray",
        settings_field="xray_bin",
        cores_field="xray",
        owner="XTLS",
        repo="Xray-core",
        version_cmd=["version"],
        version_re=re.compile(r"Xray\s+([0-9A-Za-z._-]+)"),
        archive="zip",
        binary_name="xray",
        asset_match=_xray_asset,
    ),
    CoreDef(
        name="sing-box",
        settings_field="sing_box_bin",
        cores_field="sing_box",
        owner="SagerNet",
        repo="sing-box",
        version_cmd=["version"],
        version_re=re.compile(r"sing-box\s+([0-9A-Za-z._-]+)"),
        archive="tar",
        binary_name="sing-box",
        asset_match=_singbox_asset,
    ),
    CoreDef(
        name="hysteria",
        settings_field="hysteria_bin",
        cores_field="hysteria",
        owner="apernet",
        repo="hysteria",
        version_cmd=["version"],
        version_re=re.compile(r"Version:\s+v?([0-9]+\.[0-9]+\.[0-9]+)"),
        archive="none",
        binary_name="hysteria",
        asset_match=_hysteria_asset,
    ),
]


def _installed_version(path: Path, core: CoreDef) -> str:
    if not path.exists():
        return ""
    try:
        out = subprocess.run(
            [str(path), *core.version_cmd],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        text = out.stdout or out.stderr
        match = core.version_re.search(text)
        return _norm_version(match.group(1)) if match else ""
    except Exception:
        return ""


async def _latest_release(session: aiohttp.ClientSession, core: CoreDef) -> dict | None:
    url = f"{GITHUB_API}/repos/{core.owner}/{core.repo}/releases/latest"
    try:
        async with session.get(url, headers=API_HEADERS, timeout=DOWNLOAD_TIMEOUT) as resp:
            if resp.status != 200:
                return None
            return await resp.json()
    except Exception as exc:
        log.warning("Cannot query latest %s release: %s", core.name, exc)
        return None


def _pick_asset(release: dict, core: CoreDef) -> str | None:
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        if core.asset_match(name):
            return asset.get("browser_download_url")
    return None


async def _download(session: aiohttp.ClientSession, url: str, dest: Path) -> None:
    async with session.get(url, timeout=DOWNLOAD_TIMEOUT) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as fh:
            async for chunk in resp.content.iter_chunked(1 << 16):
                fh.write(chunk)


def _extract_member(archive: Path, binary: str, dest: Path, mode: str) -> None:
    if mode == "zip":
        with zipfile.ZipFile(archive) as zf:
            names = [n for n in zf.namelist() if n.endswith("/" + binary) or n == binary]
            if not names:
                raise RuntimeError(f"{binary} not found in {archive.name}")
            with zf.open(names[0]) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
    else:
        with tarfile.open(archive, "r:gz") as tf:
            members = [m for m in tf.getmembers() if m.isfile() and m.name.endswith("/" + binary)]
            if not members:
                raise RuntimeError(f"{binary} not found in {archive.name}")
            src = tf.extractfile(members[0])
            with src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)


async def _install_core(
    session: aiohttp.ClientSession, core: CoreDef, url: str, target: Path
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    archive = target.parent / f".{core.binary_name}.download"
    tmp = target.parent / f".{core.binary_name}.tmp"
    for leftover in (archive, tmp):
        with contextlib.suppress(Exception):
            if leftover.exists():
                leftover.unlink()
    try:
        log.info("Downloading %s core from %s", core.name, url)
        await _download(session, url, archive)
        if core.archive in ("zip", "tar"):
            _extract_member(archive, core.binary_name, tmp, core.archive)
        else:
            os.replace(archive, tmp)
        os.chmod(tmp, 0o755)
        # sanity check before replacing the live binary
        out = subprocess.run(
            [str(tmp), *core.version_cmd],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if out.returncode != 0:
            raise RuntimeError(f"{core.name} downloaded binary failed version check")
        os.replace(tmp, target)
        version = _norm_version(
            core.version_re.search(out.stdout or out.stderr).group(1)
            if (out.stdout or out.stderr)
            else ""
        )
        log.info("%s core ready at %s (v%s)", core.name, target, version)
    finally:
        for leftover in (archive, tmp):
            with contextlib.suppress(Exception):
                if leftover.exists():
                    leftover.unlink()


async def ensure_cores(settings: Settings) -> Cores:
    """Return resolved core paths, downloading/updating any that are stale.

    An explicit XRAY_BIN / SING_BOX_BIN / HYSTERIA_BIN setting always wins; an
    empty value means the core is managed here under ``cores_dir``.
    """
    cores = Cores()
    if not settings.auto_update_cores:
        cores.xray = settings.xray_bin
        cores.sing_box = settings.sing_box_bin
        cores.hysteria = settings.hysteria_bin
        return cores

    cores_dir = Path(settings.cores_dir)
    async with aiohttp.ClientSession() as session:
        for core in CORE_DEFS:
            explicit = getattr(settings, core.settings_field)
            if explicit:
                setattr(cores, core.cores_field, explicit)
                log.info("%s core: explicit path %s", core.name, explicit)
                continue

            target = cores_dir / core.binary_name
            latest = ""
            installed = _installed_version(target, core)
            release = await _latest_release(session, core)
            if release is not None:
                latest = _norm_version(release.get("tag_name", ""))

            if target.exists() and installed and latest and installed == latest:
                setattr(cores, core.cores_field, str(target))
                log.info("%s core up to date (v%s)", core.name, installed)
                continue

            if release is None or not latest:
                log.warning("Could not resolve latest %s version; keeping what we have.", core.name)
                setattr(cores, core.cores_field, str(target) if target.exists() else "")
                continue

            url = _pick_asset(release, core)
            if url is None:
                log.warning("No matching asset for %s v%s; keeping existing.", core.name, latest)
                setattr(cores, core.cores_field, str(target) if target.exists() else "")
                continue

            if target.exists() and installed:
                log.info("Updating %s core: v%s -> v%s", core.name, installed, latest)
            await _install_core(session, core, url, target)
            setattr(cores, core.cores_field, str(target))
    return cores
