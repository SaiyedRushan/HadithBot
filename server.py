"""Run the Discord bot with a small HTTP health check on :8080.

The health server runs inside the bot's own asyncio event loop (aiohttp, which
discord.py already depends on), not in a separate web server with its own
threads. That matters for two reasons:

- Port 8080 is open to the internet for UptimeRobot, so scanners connect to it
  constantly, and some send half a request and then go quiet. Under gunicorn's
  gthread worker each of those held a thread forever; four of them used up all
  four threads and /health stopped answering for 2.5 hours on 2026-09-27, while
  the bot itself was fine. Here a stalled connection is one idle coroutine and
  blocks nothing.
- A response from /health now proves the bot's event loop is actually running,
  since that loop is what serves it.
"""

import asyncio
import functools
import json
import logging
import os
import signal

import discord
from aiohttp import web
from dotenv import load_dotenv

from bot import HadithBot, HadithCommands

# UptimeRobot's keyword monitor matches the literal text "bot":"online", so the
# JSON must stay compact. aiohttp's default json.dumps puts a space after the
# colon, which would make the monitor report the bot as down.
compact_json = functools.partial(json.dumps, separators=(",", ":"))

BOT_KEY = web.AppKey("bot", discord.Client)


async def home(request: web.Request) -> web.Response:
    return web.Response(text="Hello. I am alive!")


async def health(request: web.Request) -> web.Response:
    bot = request.app[BOT_KEY]
    if bot.is_closed() or not bot.is_ready():
        return web.json_response(
            {"status": "unhealthy", "bot": "offline"}, status=503, dumps=compact_json
        )
    latency = bot.latency
    return web.json_response(
        {
            "status": "healthy",
            "bot": "online",
            # latency is inf until the first heartbeat is acknowledged
            "latency": f"{latency * 1000:.2f}ms" if latency != float("inf") else "N/A",
            "guilds": len(bot.guilds),
        },
        dumps=compact_json,
    )


def make_app(bot: discord.Client) -> web.Application:
    app = web.Application()
    app[BOT_KEY] = bot
    app.router.add_get("/", home)
    app.router.add_get("/health", health)
    return app


async def start_health_server(bot: discord.Client, port: int) -> web.AppRunner:
    # keepalive_timeout: close idle kept-alive connections after 30s rather
    # than aiohttp's default of an hour.
    runner = web.AppRunner(make_app(bot), access_log=None, keepalive_timeout=30)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logging.info(f"Health server listening on :{port}")
    return runner


async def run() -> None:
    discord_token = os.getenv("DISCORD_TOKEN")
    if not discord_token:
        raise Exception("DISCORD_TOKEN is not set")

    bot = HadithBot()
    bot.tree.add_command(HadithCommands(bot))

    @bot.event
    async def on_ready():
        logging.info(f"Bot logged in as {bot.user}")

    # Python running as PID 1 in a container ignores SIGTERM unless it installs
    # a handler, so without this `docker compose down` waits 10s and kills it.
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(bot.close()))

    runner = await start_health_server(bot, int(os.getenv("PORT", "8080")))
    try:
        async with bot:
            await bot.start(discord_token)
    finally:
        await runner.cleanup()


def main() -> None:
    load_dotenv()
    # Default format on purpose: docker already timestamps each line.
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())


if __name__ == "__main__":
    main()
