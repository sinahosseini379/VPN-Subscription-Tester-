"""TCP connectivity probe used as the cheap pre-filter before Xray runs."""

from __future__ import annotations

import asyncio
import contextlib
import logging

log = logging.getLogger(__name__)


async def tcp_ping(host: str, port: int, tries: int, timeout: float = 3.0) -> int:
    """Attempt `tries` TCP connects; return the number that succeeded."""
    success = 0
    for _ in range(tries):
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
            success += 1
        except Exception:
            await asyncio.sleep(0.15)
    return success
