"""Regression test for the critical SOCKS5 bug.

aiohttp's `proxy=` kwarg only speaks HTTP proxies — tunnelling through Xray
requires an aiohttp-socks ProxyConnector. This spins up a real SOCKS5 relay
and a target HTTP server to prove requests actually go through the tunnel.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
import struct

import aiohttp
import pytest
from aiohttp_socks import ProxyConnector


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        with contextlib.suppress(Exception):
            writer.close()


async def _handle_socks(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        header = await reader.readexactly(2)
        if header[0] != 5:
            writer.close()
            return
        await reader.readexactly(header[1])
        writer.write(b"\x05\x00")
        await writer.drain()

        req = await reader.readexactly(4)
        if req[0] != 5 or req[1] != 1:  # SOCKS5 CONNECT only
            writer.close()
            return
        atyp = req[3]
        if atyp == 1:
            host = socket.inet_ntoa(await reader.readexactly(4))
        elif atyp == 3:
            ln = (await reader.readexactly(1))[0]
            host = (await reader.readexactly(ln)).decode()
        else:
            writer.close()
            return
        port = struct.unpack(">H", await reader.readexactly(2))[0]

        target_reader, target_writer = await asyncio.open_connection(host, port)
        writer.write(b"\x05\x00\x00\x01" + b"\x00" * 4 + struct.pack(">H", 0))
        await writer.drain()
        await asyncio.gather(
            _pipe(reader, target_writer),
            _pipe(target_reader, writer),
        )
    except Exception:
        writer.close()


async def _target_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    body = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"
    writer.write(body)
    await writer.drain()
    writer.close()


@pytest.mark.asyncio
async def test_proxy_connector_routes_through_socks5():
    target_server = await asyncio.start_server(_target_handler, "127.0.0.1", 0)
    socks_server = await asyncio.start_server(_handle_socks, "127.0.0.1", 0)
    target_port = target_server.sockets[0].getsockname()[1]
    socks_port = socks_server.sockets[0].getsockname()[1]

    proxy_url = f"socks5://127.0.0.1:{socks_port}"
    connector = ProxyConnector.from_url(proxy_url, rdns=True)
    try:
        async with (
            aiohttp.ClientSession(connector=connector) as session,
            session.get(f"http://127.0.0.1:{target_port}/") as resp,
        ):
            assert resp.status == 200
            assert await resp.text() == "ok"
    finally:
        await connector.close()
        target_server.close()
        socks_server.close()
        await target_server.wait_closed()
        await socks_server.wait_closed()
