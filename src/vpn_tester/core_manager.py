"""Core management: download, version check, and auto-update for Xray, Sing-box, and Hysteria."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from .config import Settings

log = logging.getLogger(__name__)

CORE_DIR_NAME = "cores"
XRAY_CORE_NAME = "xray"
SING_BOX_CORE_NAME = "sing-box"
HYSTERIA_CORE_NAME = "hysteria"

GITHUB_API_BASE = "https://api.github.com/repos"

CORE_REPOS = {
    XRAY_CORE_NAME: "XTLS/Xray-core",
    SING_BOX_CORE_NAME: "SagerNet/sing-box",
    HYSTERIA_CORE_NAME: "apernet/hysteria",
}

ASSET_PATTERNS = {
    XRAY_CORE_NAME: [r"xray-linux-64\.zip$"],
    SING_BOX_CORE_NAME: [r"sing-box-.*-linux-amd64\.tar\.gz$"],
    HYSTERIA_CORE_NAME: [r"hysteria-linux-amd64(\.tar\.gz|\.zip)$"],
}

BINARY_NAMES = {
    XRAY_CORE_NAME: "xray",
    SING_BOX_CORE_NAME: "sing-box",
    HYSTERIA_CORE_NAME: "hysteria",
}


class CoreManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.cores_dir = Path(settings.config_file).parent / CORE_DIR_NAME
        self.cores_dir.mkdir(parents=True, exist_ok=True)

    def _core_path(self, name: str) -> Path:
        return self.cores_dir / name / BINARY_NAMES[name]

    def _version_file(self, name: str) -> Path:
        return self.cores_dir / name / "version.txt"

    def _get_local_version(self, name: str) -> str | None:
        vf = self._version_file(name)
        if vf.exists():
            return vf.read_text().strip()
        binary = self._core_path(name)
        if binary.exists():
            try:
                result = subprocess.run(
                    [str(binary), "version"], capture_output=True, text=True, timeout=10
                )
                out = result.stdout or result.stderr
                m = re.search(r"(\d+\.\d+\.\d+)", out)
                if m:
                    return m.group(1)
            except Exception:
                pass
        return None

    async def _get_latest_release(self, session: aiohttp.ClientSession, repo: str) -> dict | None:
        url = f"{GITHUB_API_BASE}/{repo}/releases/latest"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            log.warning("Failed to fetch latest release for %s: %s", repo, e)
        return None

    def _find_asset_url(self, release: dict, name: str) -> str | None:
        patterns = ASSET_PATTERNS.get(name, [])
        for asset in release.get("assets", []):
            asset_name = asset.get("name", "")
            for pattern in patterns:
                if re.search(pattern, asset_name):
                    return asset.get("browser_download_url")
        return None

    async def _download_and_extract(
        self, session: aiohttp.ClientSession, url: str, dest_dir: Path, name: str
    ) -> Path | None:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    log.error("Download failed: HTTP %s", resp.status)
                    return None
                data = await resp.read()
        except Exception as e:
            log.error("Download error for %s: %s", name, e)
            return None

        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "archive"
            archive_path.write_bytes(data)

            if url.endswith(".zip"):
                import zipfile

                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(tmp)
            elif url.endswith(".tar.gz") or url.endswith(".tgz"):
                import tarfile

                with tarfile.open(archive_path, "r:gz") as tf:
                    tf.extractall(tmp)

            binary_name = BINARY_NAMES[name]
            for root, _, files in os.walk(tmp):
                for f in files:
                    if f == binary_name or f.startswith(binary_name + "."):
                        src = Path(root) / f
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        dest = dest_dir / binary_name
                        shutil.move(str(src), str(dest))
                        dest.chmod(0o755)
                        return dest
        log.error("Binary %s not found in archive from %s", binary_name, url)
        return None

    async def ensure_core(self, name: str) -> Path | None:
        """Download core if missing, return path to binary."""
        local_ver = self._get_local_version(name)
        core_path = self._core_path(name)
        if core_path.exists() and local_ver:
            log.info("%s already installed (v%s)", name, local_ver)
            return core_path

        repo = CORE_REPOS.get(name)
        if not repo:
            log.error("Unknown core: %s", name)
            return None

        log.info("Downloading %s...", name)
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            release = await self._get_latest_release(session, repo)
            if not release:
                return None
            tag = release.get("tag_name", "")
            version = tag.lstrip("v")
            asset_url = self._find_asset_url(release, name)
            if not asset_url:
                log.error("No matching asset for %s in release %s", name, tag)
                return None

            core_dir = self.cores_dir / name
            if core_dir.exists():
                shutil.rmtree(core_dir)
            binary = await self._download_and_extract(session, asset_url, core_dir, name)
            if binary:
                self._version_file(name).write_text(version)
                log.info("Installed %s v%s to %s", name, version, binary)
                return binary
        return None

    async def check_and_update_all(self) -> dict[str, bool]:
        """Check all cores for updates, download if newer. Returns dict of core->updated."""
        results = {}
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for name in [XRAY_CORE_NAME, SING_BOX_CORE_NAME, HYSTERIA_CORE_NAME]:
                repo = CORE_REPOS.get(name)
                if not repo:
                    continue
                local_ver = self._get_local_version(name)
                release = await self._get_latest_release(session, repo)
                if not release:
                    results[name] = False
                    continue
                tag = release.get("tag_name", "")
                latest_ver = tag.lstrip("v")
                if local_ver and local_ver == latest_ver:
                    log.info("%s up to date (v%s)", name, local_ver)
                    results[name] = False
                    continue
                asset_url = self._find_asset_url(release, name)
                if not asset_url:
                    results[name] = False
                    continue
                core_dir = self.cores_dir / name
                if core_dir.exists():
                    shutil.rmtree(core_dir)
                binary = await self._download_and_extract(session, asset_url, core_dir, name)
                if binary:
                    self._version_file(name).write_text(latest_ver)
                    log.info("Updated %s to v%s", name, latest_ver)
                    results[name] = True
                else:
                    results[name] = False
        return results

    def get_core_path(self, name: str) -> Path | None:
        """Return path to binary if exists, else None."""
        p = self._core_path(name)
        return p if p.exists() else None


async def ensure_all_cores(settings: Settings) -> dict[str, Path]:
    """Convenience: ensure all three cores, return name->path dict."""
    mgr = CoreManager(settings)
    results = {}
    for name in [XRAY_CORE_NAME, SING_BOX_CORE_NAME, HYSTERIA_CORE_NAME]:
        p = await mgr.ensure_core(name)
        if p:
            results[name] = p
    return results


async def check_and_update_cores(settings: Settings) -> dict[str, bool]:
    mgr = CoreManager(settings)
    return await mgr.check_and_update_all()
