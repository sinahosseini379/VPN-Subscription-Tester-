"""Manage a single proxy-core process per config.

- Picks the right core for the config's protocol (hysteria2 -> hysteria,
  everything else -> Xray, with sing-box as a fallback when Xray is absent).
- Launches the core with a per-config config file and a unique local SOCKS5 port.
- Waits for the SOCKS port to actually accept connections (readiness polling).
- Guarantees process + temp-dir cleanup via async context manager and exit hooks.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import shutil
import signal
import tempfile
import time

import aiohttp
from aiohttp_socks import ProxyConnector

from .config import Settings
from .cores import Cores
from .models import Config
from .parsers import build_hysteria_client_config, build_singbox_config, build_xray_config

log = logging.getLogger(__name__)

_active_procs: set[asyncio.subprocess.Process] = set()

# (protocol, core) -> config builder + launch args. hysteria2 always prefers the
# dedicated hysteria core; the rest run on xray (sing-box only as a fallback).
_BUILDERS = {
    "hysteria2": build_hysteria_client_config,
    "sing-box": build_singbox_config,
    "xray": build_xray_config,
}

# Core -> (subcommand argv, config flag).
_CORE_LAUNCH = {
    "xray": (["run"], "-config"),
    "sing-box": (["run"], "-c"),
    "hysteria": (["client"], "-c"),
}


def _cleanup_all() -> None:
    """Best-effort kill of every tracked core process (used on fatal exits)."""
    for proc in list(_active_procs):
        with contextlib.suppress(Exception):
            proc.kill()


def install_signal_handlers() -> None:
    """Register SIGINT/SIGTERM so orphaned core processes are cleaned up."""
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, RuntimeError):
            asyncio.get_running_loop().add_signal_handler(sig, _cleanup_all)


async def wait_for_port(host: str, port: int, timeout: float, poll_interval: float = 0.2) -> bool:
    """Return True once a TCP listener answers on host:port within timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=poll_interval + 0.1
            )
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
            return True
        except Exception:
            await asyncio.sleep(poll_interval)
    return False


class CoreRunner:
    """Runs one config through the most appropriate proxy core binary."""

    def __init__(self, cores: Cores, cfg: Config, socks_port: int, settings: Settings):
        self.cores = cores
        self.cfg = cfg
        self.socks_port = socks_port
        self.settings = settings
        self.proxy_url = f"socks5://127.0.0.1:{socks_port}"
        self.core_bin = ""
        self._subcmd: list[str] = []
        self._cfg_flag = ""
        self._proc: asyncio.subprocess.Process | None = None
        self._tmpdir: str | None = None
        self._connector: ProxyConnector | None = None
        self._session: aiohttp.ClientSession | None = None

    def _resolve_core(self) -> str:
        """Pick the binary for this config's protocol, honouring Xray first."""
        proto = self.cfg.protocol
        if proto == "hysteria2" and self.cores.hysteria:
            return self.cores.hysteria
        if self.cores.xray:
            return self.cores.xray
        if self.cores.sing_box:
            return self.cores.sing_box
        raise RuntimeError(
            f"No usable core for {proto}. Managed cores are downloaded automatically; "
            "set XRAY_BIN/SING_BOX_BIN/HYSTERIA_BIN to use system binaries."
        )

    def _write_config(self) -> str:
        """Write the per-core config file and return its path."""
        self._tmpdir = tempfile.mkdtemp(prefix="core_")

        if self.core_bin == self.cores.hysteria and self.cores.hysteria:
            config_text = _BUILDERS["hysteria2"](
                self.cfg.uri, self.socks_port, allow_insecure=self.settings.allow_insecure
            )
            if config_text is None:
                raise ValueError(f"Cannot build hysteria client config for {self.cfg.uri[:60]}")
            self._subcmd, self._cfg_flag = _CORE_LAUNCH["hysteria"]
            cfg_path = os.path.join(self._tmpdir, "config.yaml")
            with open(cfg_path, "w", encoding="utf-8") as fh:
                fh.write(config_text)
            return cfg_path

        use_singbox = bool(self.cores.sing_box) and self.core_bin == self.cores.sing_box
        builder = _BUILDERS["sing-box"] if use_singbox else _BUILDERS["xray"]
        config = builder(self.cfg.uri, self.socks_port, allow_insecure=self.settings.allow_insecure)
        if config is None:
            raise ValueError(f"Cannot build core config for {self.cfg.uri[:60]}")
        self._subcmd, self._cfg_flag = (
            _CORE_LAUNCH["sing-box"] if use_singbox else _CORE_LAUNCH["xray"]
        )
        cfg_path = os.path.join(self._tmpdir, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(config, fh)
        return cfg_path

    async def _launch(self, cfg_path: str) -> None:
        args = [
            self.core_bin,
            *self._subcmd,
            self._cfg_flag,
            cfg_path,
            *self.settings.xray_extra_args,
        ]
        self._proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        _active_procs.add(self._proc)

    @property
    def session(self) -> aiohttp.ClientSession:
        """HTTP session whose traffic is tunnelled through this config's SOCKS port.

        aiohttp's `proxy=` kwarg only supports HTTP proxies, so each runner owns a
        dedicated aiohttp-socks ProxyConnector (rdns=True keeps DNS inside the
        tunnel, avoiding leaks and false results).
        """
        if self._session is None:
            raise RuntimeError("session not available before __aenter__")
        return self._session

    async def __aenter__(self) -> CoreRunner:
        self.core_bin = self._resolve_core()
        cfg_path = self._write_config()
        await self._launch(cfg_path)

        ready = await wait_for_port(
            "127.0.0.1", self.socks_port, self.settings.xray_startup_timeout
        )
        if not ready:
            raise RuntimeError(
                f"Core {os.path.basename(self.core_bin)} did not open the SOCKS port in time"
            )

        self._connector = ProxyConnector.from_url(self.proxy_url, rdns=True)
        self._session = aiohttp.ClientSession(connector=self._connector)
        return self

    async def __aexit__(self, *_):
        if self._session:
            await self._session.close()
            self._session = None
        if self._connector:
            await self._connector.close()
            self._connector = None
        if self._proc:
            try:
                self._proc.kill()
                await asyncio.wait_for(self._proc.wait(), timeout=3)
            except Exception:
                pass
            _active_procs.discard(self._proc)
            self._proc = None
        if self._tmpdir:
            shutil.rmtree(self._tmpdir, ignore_errors=True)
            self._tmpdir = None

    async def test_url(self, label: str, url: str) -> float | None:
        """One validated HTTP request through the SOCKS proxy.

        Only 2xx/3xx responses count as success; returns latency ms or None.
        """
        timeout = aiohttp.ClientTimeout(
            connect=self.settings.connect_timeout,
            total=self.settings.request_timeout,
        )
        try:
            t0 = time.perf_counter()
            async with self.session.get(
                url,
                timeout=timeout,
                allow_redirects=True,
                ssl=False,
            ) as resp:
                if resp.status < 200 or resp.status >= 400:
                    return None
                await resp.read()
            return (time.perf_counter() - t0) * 1000.0
        except Exception:
            return None


# Backwards-compatible alias for older importers.
XrayRunner = CoreRunner
