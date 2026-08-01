"""Manage a single Xray process per config.

- Launches Xray with a per-config JSON and a unique local SOCKS5 port.
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
from .models import Config
from .parsers import build_xray_config

log = logging.getLogger(__name__)

_active_procs: set[asyncio.subprocess.Process] = set()


def _cleanup_all() -> None:
    """Best-effort kill of every tracked Xray process (used on fatal exits)."""
    for proc in list(_active_procs):
        with contextlib.suppress(Exception):
            proc.kill()


def install_signal_handlers() -> None:
    """Register SIGINT/SIGTERM so orphaned Xray processes are cleaned up."""
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


class XrayRunner:
    def __init__(self, xray_bin: str, cfg: Config, socks_port: int, settings: Settings):
        self.xray_bin = xray_bin
        self.cfg = cfg
        self.socks_port = socks_port
        self.settings = settings
        self.proxy_url = f"socks5://127.0.0.1:{socks_port}"
        self._proc: asyncio.subprocess.Process | None = None
        self._tmpdir: str | None = None
        self._connector: ProxyConnector | None = None
        self._session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        """HTTP session whose traffic is tunnelled through this config's SOCKS port.

        aiohttp's `proxy=` kwarg only supports HTTP proxies, so each Xray runner
        owns a dedicated aiohttp-socks ProxyConnector (rdns=True keeps DNS inside
        the tunnel, avoiding leaks and false results).
        """
        if self._session is None:
            raise RuntimeError("session not available before __aenter__")
        return self._session

    async def __aenter__(self) -> XrayRunner:
        xray_cfg = build_xray_config(
            self.cfg.uri, self.socks_port, allow_insecure=self.settings.allow_insecure
        )
        if xray_cfg is None:
            raise ValueError(f"Cannot build Xray config for {self.cfg.uri[:60]}")
        self._tmpdir = tempfile.mkdtemp(prefix="xray_")
        cfg_path = os.path.join(self._tmpdir, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump(xray_cfg, fh)

        args = [self.xray_bin, "run", "-config", cfg_path, *self.settings.xray_extra_args]
        self._proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        _active_procs.add(self._proc)

        ready = await wait_for_port(
            "127.0.0.1", self.socks_port, self.settings.xray_startup_timeout
        )
        if not ready:
            raise RuntimeError("Xray did not open the SOCKS port in time")

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
