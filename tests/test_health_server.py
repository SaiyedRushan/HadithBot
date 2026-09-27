"""The /health endpoint UptimeRobot checks.

The bot is replaced by a stub with the four attributes the handler reads, so no
Discord connection is needed. Each test runs the real aiohttp server on a free
local port and talks to it over plain sockets.
"""

import asyncio
from types import SimpleNamespace

from aiohttp.test_utils import unused_port

from server import start_health_server


def fake_bot(*, ready=True, closed=False):
    return SimpleNamespace(
        is_ready=lambda: ready,
        is_closed=lambda: closed,
        latency=0.035,
        guilds=[object()] * 16,
    )


async def get(port, path):
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    raw = await asyncio.wait_for(reader.read(), timeout=5)
    writer.close()
    return raw.decode()


def serve(bot, scenario):
    async def main():
        port = unused_port()
        runner = await start_health_server(bot, port)
        try:
            return await scenario(port)
        finally:
            await runner.cleanup()

    return asyncio.run(main())


def test_health_matches_the_uptimerobot_keyword():
    # The monitor alerts unless this exact text is in the body, so a space
    # after the colon would page for a bot that's actually up.
    response = serve(fake_bot(), lambda port: get(port, "/health"))
    assert response.startswith("HTTP/1.1 200")
    assert '"bot":"online"' in response
    assert '"guilds":16' in response


def test_health_is_503_until_the_bot_is_ready():
    response = serve(fake_bot(ready=False), lambda port: get(port, "/health"))
    assert response.startswith("HTTP/1.1 503")
    assert '"bot":"online"' not in response


def test_stalled_connections_do_not_block_health():
    # What took the old gunicorn server down: scanners that send part of a
    # request and then go quiet. Four of them filled all four threads.
    async def scenario(port):
        stalled = []
        for _ in range(20):
            _, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b"GET / HTTP/1.1\r\nHost: x\r\n")  # never finished
            await writer.drain()
            stalled.append(writer)
        try:
            return await get(port, "/health")
        finally:
            for writer in stalled:
                writer.close()

    response = serve(fake_bot(), scenario)
    assert response.startswith("HTTP/1.1 200")
    assert '"bot":"online"' in response
