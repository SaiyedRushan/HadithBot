"""The API behind the daily name match game (the Activity in ``activity/``).

Served by the bot's own aiohttp server (server.py), under ``/api``. The game
is hosted on Vercel at play.hadithbot.app, whose ``/api/*`` is rewritten to
api.hadithbot.app (Caddy on the VM, in front of port 8080), so inside
Discord's proxy every request is same-origin.

Living in the bot process means the card edits go through discord.py, which
already handles Discord's rate limits, and the card is rendered by the same
code (name_match.card_embed) the 6 PM broadcast uses.

The database is passed in as ``store`` (the db module in production) so tests
can run without credentials.
"""

import asyncio
import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional

import aiohttp
import discord
from aiohttp import web

import activity_token
import name_match
from views import build_name_match_view

logger = logging.getLogger("HadithBot")

DISCORD_API = "https://discord.com/api/v10"
# A run started before the 6 PM broadcast closed its match still counts if it
# lands within this long after.
LATE_GRACE = timedelta(minutes=15)
CARD_EDIT_DELAY = 2.0

Exchange = Callable[[str], Awaitable[dict]]


def name_match_channels() -> Optional[set[str]]:
    """Which channels get the daily card, from NAME_MATCH_CHANNELS.

    Unset or empty: none (the feature is off). ``*``: every channel that hasn't
    turned it off. Otherwise a comma-separated list of channel ids, for testing
    in one channel before it goes out everywhere.
    """
    raw = (os.getenv("NAME_MATCH_CHANNELS") or "").strip()
    if not raw:
        return set()
    if raw == "*":
        return None
    return {c.strip() for c in raw.split(",") if c.strip()}


def name_match_on(channel_row: dict) -> bool:
    allowed = name_match_channels()
    if allowed is not None and str(channel_row.get("channel_id")) not in allowed:
        return False
    return channel_row.get("name_match_enabled", True) is not False


def _error(status: int, message: str) -> web.Response:
    return web.json_response({"error": message}, status=status)


async def _run(fn, *args):
    """Supabase's client is synchronous; keep it off the bot's event loop."""
    return await asyncio.to_thread(fn, *args)


async def render_card(store, day: dict, *, final: bool) -> discord.Embed:
    cid, key = day["channel_id"], str(day["day_key"])
    results = await _run(store.get_game_results, cid, key)
    others = {g: await _run(store.get_game_results, cid, key, g) for g in name_match.GAME_ORDER[1:]}
    played = [] if final else await _run(store.get_played_day_keys, cid)
    return name_match.card_embed(day, results, final=final, played_keys=played, others=others)


async def edit_card(bot, store, day: dict, *, final: bool) -> bool:
    """Re-render a day's card in place. False if the message is gone."""
    if not day.get("message_id"):
        return False
    channel = bot.get_channel(int(day["channel_id"]))
    if channel is None:
        return False
    embed = await render_card(store, day, final=final)
    message = channel.get_partial_message(int(day["message_id"]))
    try:
        await message.edit(embed=embed, view=build_name_match_view(final=final))
        return True
    except discord.HTTPException as e:
        logger.warning(f"Couldn't edit name match card {day['message_id']}: {e}")
        return False


def _subtitle(items: dict) -> str:
    pairs = name_match.all_pairs(items)
    first, last = pairs[0]["id"], pairs[-1]["id"]
    names = items.get("today_names") or []
    if len(names) == 1:
        today = f", including today's name, {names[0]}"
    elif names:
        today = f", including today's names, {', '.join(names[:-1])} and {names[-1]}"
    else:
        today = ""
    return (
        f"Names {first} to {last}{today}. "
        f"Everyone in this server gets the same {len(pairs)}."
    )


def _surah_subtitle(items: dict) -> str:
    n = len(name_match.all_pairs(items))
    return f"{n} surahs of the Quran. Everyone in this server gets the same {n} today."


def _client_sets(items: dict) -> list[dict]:
    titles = {k: g["play"] for k, g in name_match.GAMES.items()}
    return [
        {
            "kind": s["kind"],
            "title": titles.get(s["kind"], "Match the pairs"),
            "pairs": [
                {
                    "id": p["id"],
                    "left": p["left"],
                    "leftAr": p.get("left_ar"),
                    "right": p["right"],
                }
                for p in s["pairs"]
            ],
        }
        for s in items["sets"]
    ]


class RateLimit:
    """At most ``limit`` calls per ``window`` seconds per key, in memory."""

    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self.hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        recent = [t for t in self.hits.get(key, []) if now - t < self.window]
        if len(recent) >= self.limit:
            self.hits[key] = recent
            return False
        recent.append(now)
        self.hits[key] = recent
        if len(self.hits) > 10_000:
            self.hits.clear()
        return True


class GameApi:
    def __init__(
        self,
        bot,
        store,
        *,
        token_secret: str,
        exchange: Exchange,
    ):
        self.bot = bot
        self.store = store
        self.secret = token_secret
        self.exchange = exchange
        self.limits = RateLimit(30, 60)
        # Every sign-in arrives from Discord's proxy by way of Vercel, so there's
        # no per-person address to limit by. This only caps a flood.
        self.signin_limit = RateLimit(300, 60)
        self.log_limit = RateLimit(60, 60)
        self._pending_edits: set[tuple[str, str]] = set()
        self.surahs = name_match.load_surahs()

    def routes(self) -> list[web.RouteDef]:
        return [
            web.post("/api/token", self.token),
            web.get("/api/today", self.today),
            web.post("/api/result", self.result),
            web.post("/api/client-log", self.client_log),
        ]

    # --- helpers ---------------------------------------------------------

    def _claims(self, request: web.Request) -> Optional[dict]:
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return None
        return activity_token.verify(self.secret, header[len("Bearer ") :])

    def _game_items(self, game: str, day: Optional[dict]) -> dict:
        """The pairs for one game: the day's frozen names, or the day's surahs.

        Without a day (practice), a random 10.
        """
        size = name_match.MATCH_SIZE
        if game == "surahs":
            numbers = (
                name_match.pick_surahs(str(day["day_key"]))
                if day
                else sorted(random.sample(range(1, len(self.surahs) + 1), size))
            )
            return name_match.build_surah_items(self.surahs, numbers)
        if day:
            return day["items"]
        names = sorted(random.sample(self.bot.names, size), key=lambda n: n.number)
        return name_match.build_items(self.bot.names, [n.number for n in names], [])

    def _games_list(self, mine: dict, *, practice: bool = False) -> list[dict]:
        """Today's games for the picker: what each is and your score in it."""
        practice_detail = {
            "names": "10 names of Allah, picked at random",
            "surahs": "10 surahs of the Quran, picked at random",
        }
        return [
            {
                "key": k,
                "title": name_match.GAMES[k]["title"],
                "detail": practice_detail[k] if practice else name_match.GAMES[k]["detail"],
                "count": name_match.MATCH_SIZE,
                "myResult": name_match.result_payload(mine[k]) if mine.get(k) else None,
            }
            for k in name_match.GAME_ORDER
        ]

    def _practice(self, claims: dict, game: str = "names") -> dict:
        items = self._game_items(game, None)
        noun = "surahs of the Quran" if game == "surahs" else "names of Allah"
        return {
            "mode": "practice",
            "game": game,
            "games": self._games_list({}, practice=True),
            "dayKey": None,
            "channelName": None,
            "title": f"Practice: match 10 {noun}",
            # The game prints its own "not scored" paragraph for practice.
            "subtitle": None,
            "sets": _client_sets(items),
            "myResult": None,
            "board": [],
            "nextMatch": name_match.NEXT_MATCH_TEXT,
            "mugupUrl": name_match.GAMES[game]["mugup"],
        }

    def _channel_name(self, channel_id: str) -> Optional[str]:
        channel = self.bot.get_channel(int(channel_id))
        return getattr(channel, "name", None)

    def schedule_card_edit(self, day: dict) -> None:
        """Edit the card soon, once, however many runs land in the meantime.

        A burst of people finishing together would otherwise be one edit each
        and run into Discord's per-channel limit. The edit re-renders from every
        stored result, so it always shows the latest state.
        """
        key = (str(day["channel_id"]), str(day["day_key"]))
        if key in self._pending_edits:
            return
        self._pending_edits.add(key)

        async def later():
            try:
                await asyncio.sleep(CARD_EDIT_DELAY)
                fresh = await _run(self.store.get_game_day, *key)
                if fresh:
                    await edit_card(
                        self.bot, self.store, fresh, final=bool(fresh.get("closed_at"))
                    )
            except Exception:
                logger.error("Name match card edit failed", exc_info=True)
            finally:
                self._pending_edits.discard(key)

        asyncio.get_running_loop().create_task(later())

    # --- routes ----------------------------------------------------------

    async def token(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:
            return _error(400, "The game sent a request it shouldn't have. Close it and open it again.")
        code = body.get("code") if isinstance(body, dict) else None
        if not isinstance(code, str) or not code:
            return _error(400, "Discord didn't send a sign-in code. Close the game and open it again.")
        if not self.signin_limit.allow("all"):
            return _error(429, "Too many sign-ins at once. Wait a minute and open the game again.")
        try:
            user = await self.exchange(code)
        except Exception:
            logger.warning("Activity sign-in failed", exc_info=True)
            return _error(401, "Discord sign-in didn't work. Close the game and open it again.")

        guild_id = body.get("guildId") or None
        channel_id = body.get("channelId") or None
        if guild_id and channel_id:
            channel = self.bot.get_channel(int(channel_id))
            guild = getattr(channel, "guild", None)
            if guild is None or str(guild.id) != str(guild_id):
                # Not a channel HadithBot can see, or a mismatched pair: the
                # game still opens, as a practice round with nothing posted.
                guild_id = channel_id = None
            else:
                try:
                    await guild.fetch_member(int(user["id"]))
                except discord.NotFound:
                    return _error(403, "You need to be a member of this server to play its match.")
                except discord.HTTPException:
                    pass  # can't check right now; don't lock people out for it

        display = user.get("global_name") or user.get("username") or "Someone"
        claims = {"uid": str(user["id"]), "name": display[:80], "gid": guild_id, "cid": channel_id}
        token = activity_token.mint(self.secret, claims)
        return web.json_response(
            {"token": token, "player": {"id": claims["uid"], "displayName": claims["name"]}}
        )

    async def client_log(self, request: web.Request) -> web.Response:
        """Why a game couldn't start on someone's screen (activity/src/discord.ts).

        Unauthenticated, because it reports failures from before sign-in, so it
        only ever writes a short line to the log.
        """
        if self.log_limit.allow("all"):
            try:
                text = (await request.text())[:600]
            except Exception:
                text = "<unreadable>"
            logger.warning(f"Name match game couldn't start: {text}")
        return web.Response(status=204)

    async def today(self, request: web.Request) -> web.Response:
        claims = self._claims(request)
        if claims is None:
            return _error(401, "Your sign-in ran out. Close the game and open it again.")
        game = request.query.get("game", "names")
        if game not in name_match.GAMES:
            return _error(404, "That game isn't in today's match. Close the game and open it again.")
        cid = claims.get("cid")
        if not cid:
            return web.json_response(self._practice(claims, game))
        row = await _run(self.store.get_channel_state, cid)
        day = await _run(self.store.get_open_game_day, cid)
        if not day or not row or not name_match_on(row):
            return web.json_response(self._practice(claims, game))

        key = str(day["day_key"])
        mine = {
            g: await _run(self.store.get_game_result, cid, key, claims["uid"], g)
            for g in name_match.GAME_ORDER
        }
        results = await _run(self.store.get_game_results, cid, key, game)
        items = self._game_items(game, day)
        return web.json_response(
            {
                "mode": "daily",
                "game": game,
                "games": self._games_list(mine),
                "dayKey": key,
                "channelName": self._channel_name(cid),
                "title": name_match.GAMES[game]["play"],
                "subtitle": _surah_subtitle(items) if game == "surahs" else _subtitle(items),
                "sets": _client_sets(items),
                "myResult": name_match.result_payload(mine[game]) if mine[game] else None,
                "board": name_match.board_rows(results, claims["uid"]),
                "nextMatch": name_match.NEXT_MATCH_TEXT,
                "mugupUrl": name_match.GAMES[game]["mugup"],
            }
        )

    async def result(self, request: web.Request) -> web.Response:
        claims = self._claims(request)
        if claims is None:
            return _error(401, "Your sign-in ran out, so this score wasn't saved. Close the game and open it again.")
        cid = claims.get("cid")
        if not cid:
            return _error(400, "Practice rounds aren't posted anywhere.")
        if not self.limits.allow(f"user:{claims['uid']}"):
            return _error(429, "Too many requests. Wait a minute and try again.")
        try:
            body = await request.json()
            day_key = str(body["dayKey"])
            game = str(body.get("game") or "names")
            if game not in name_match.GAMES:
                raise ValueError
            guesses = body.get("guesses") or []
            duration = body.get("durationMs")
            if not isinstance(guesses, list):
                raise ValueError
        except Exception:
            return _error(400, "The game sent a score it shouldn't have. Close it and open it again.")

        day = await _run(self.store.get_game_day, cid, day_key)
        if not day:
            return _error(404, "This match isn't in this channel. Open the game from today's card.")
        closed = day.get("closed_at")
        if closed:
            closed_at = datetime.fromisoformat(str(closed).replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - closed_at > LATE_GRACE:
                return _error(
                    409,
                    "This match has closed. Today's match is in the newest message from HadithBot.",
                )

        try:
            items = self._game_items(game, day)
            score, item_results = name_match.score_guesses(items, guesses)
            duration_ms = name_match.check_duration(duration, item_results)
        except name_match.InvalidRun as e:
            logger.warning(f"Rejected name match run from {claims['uid']}: {e}")
            return _error(400, "That run couldn't be scored, so it wasn't posted.")

        record: dict[str, Any] = {
            "channel_id": cid,
            "day_key": day_key,
            "guild_id": claims.get("gid"),
            "discord_user_id": claims["uid"],
            "display_name": claims["name"],
            "score": score,
            "total": len(item_results),
            "item_results": item_results,
            "guesses": guesses,
            "duration_ms": duration_ms,
            "game": game,
        }
        saved, recorded = await _run(self.store.insert_game_result, record)
        if recorded:
            if not day.get("played"):
                await _run(self.store.mark_game_day_played, cid, day_key)
            self.schedule_card_edit(day)
        results = await _run(self.store.get_game_results, cid, day_key, game)
        mine = {
            g: saved if g == game else await _run(self.store.get_game_result, cid, day_key, claims["uid"], g)
            for g in name_match.GAME_ORDER
        }
        return web.json_response(
            {
                "result": name_match.result_payload(saved),
                "recorded": recorded,
                "games": self._games_list(mine),
                "board": name_match.board_rows(results, claims["uid"]),
            }
        )


def discord_exchange(client_id: str, client_secret: str) -> Exchange:
    """Trade an Activity's authorize code for the player's Discord identity."""

    async def exchange(code: str) -> dict:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{DISCORD_API}/oauth2/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                },
            ) as r:
                if r.status != 200:
                    raise RuntimeError(f"token exchange {r.status}: {await r.text()}")
                access = (await r.json())["access_token"]
            async with session.get(
                f"{DISCORD_API}/users/@me", headers={"Authorization": f"Bearer {access}"}
            ) as r:
                if r.status != 200:
                    raise RuntimeError(f"users/@me {r.status}")
                return await r.json()

    return exchange


def game_routes_from_env(bot) -> list[web.RouteDef]:
    """The API's routes, or none when the Activity isn't configured here."""
    secret = os.getenv("ACTIVITY_TOKEN_SECRET") or ""
    client_secret = os.getenv("DISCORD_CLIENT_SECRET") or ""
    client_id = os.getenv("DISCORD_CLIENT_ID") or ""
    if len(secret) < 32 or not client_secret or not client_id:
        return []
    import db  # imported here: see views.py's docstring

    api = GameApi(bot, db, token_secret=secret, exchange=discord_exchange(client_id, client_secret))
    bot.game_api = api
    return api.routes()
