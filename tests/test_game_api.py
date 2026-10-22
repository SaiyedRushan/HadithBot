"""The name match API, against a fake store and a stub bot (no Discord, no database)."""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import activity_token
import game_api
import name_match as nm
from utils import Name

NAMES = [Name(**n) for n in json.loads(Path("data/99names.json").read_text())]
SECRET = "s" * 40
CID, GID = "555", "777"


class FakeStore:
    def __init__(self):
        self.days = {}
        self.results = {}
        self.channels = {CID: {"channel_id": CID, "name_match_enabled": True}}

    def get_channel_state(self, cid):
        return self.channels.get(cid)

    def get_open_game_day(self, cid):
        open_days = [d for (c, _), d in self.days.items() if c == cid and not d.get("closed_at")]
        return max(open_days, key=lambda d: d["day_key"]) if open_days else None

    def get_game_day(self, cid, key):
        return self.days.get((cid, key))

    def get_game_results(self, cid, key):
        return [r for (c, k, _), r in self.results.items() if (c, k) == (cid, key)]

    def get_game_result(self, cid, key, uid):
        return self.results.get((cid, key, uid))

    def insert_game_result(self, record):
        k = (record["channel_id"], record["day_key"], record["discord_user_id"])
        if k in self.results:
            return self.results[k], False
        self.results[k] = dict(record, created_at="2026-10-22T22:00:00")
        return self.results[k], True

    def mark_game_day_played(self, cid, key):
        self.days[(cid, key)]["played"] = True

    def get_played_day_keys(self, cid):
        return [k for (c, k), d in self.days.items() if c == cid and d.get("played")]


def make_bot():
    guild = SimpleNamespace(id=int(GID))

    async def fetch_member(uid):
        return object()

    guild.fetch_member = fetch_member
    channel = SimpleNamespace(id=int(CID), name="daily-hadith", guild=guild)
    return SimpleNamespace(
        names=NAMES, get_channel=lambda i: channel if str(i) == CID else None
    )


EDITS = []


@pytest.fixture(autouse=True)
def everywhere(monkeypatch):
    monkeypatch.setenv("NAME_MATCH_CHANNELS", "*")
    monkeypatch.setattr(game_api, "CARD_EDIT_DELAY", 0)
    EDITS.clear()

    async def fake_edit(bot, store, day, *, final):
        EDITS.append((day["day_key"], final))
        return True

    monkeypatch.setattr(game_api, "edit_card", fake_edit)


def serve(store, scenario, user=None):
    user = user or {"id": "42", "global_name": "Saif", "username": "saif"}

    async def exchange(code):
        if code == "bad":
            raise RuntimeError("nope")
        return user

    async def main():
        api = game_api.GameApi(make_bot(), store, token_secret=SECRET, exchange=exchange)
        app = web.Application()
        app.add_routes(api.routes())
        async with TestClient(TestServer(app)) as client:
            out = await scenario(client)
            await asyncio.sleep(0.05)
            return out, list(EDITS)

    return asyncio.run(main())


def add_day(store, key="2026-10-22", **extra):
    day = {
        "channel_id": CID,
        "day_key": key,
        "items": nm.build_items(NAMES, nm.pick_names(58), [58]),
        "message_id": "9",
        **extra,
    }
    store.days[(CID, key)] = day
    return day


async def sign_in(client, channel=CID, guild=GID, code="ok"):
    r = await client.post("/api/token", json={"code": code, "guildId": guild, "channelId": channel})
    return r.status, await r.json()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_sign_in_seals_the_channel():
    async def scenario(client):
        status, body = await sign_in(client)
        claims = activity_token.verify(SECRET, body["token"])
        return status, body, claims

    (status, body, claims), _ = serve(FakeStore(), scenario)
    assert status == 200 and body["player"] == {"id": "42", "displayName": "Saif"}
    assert claims["cid"] == CID and claims["gid"] == GID


def test_failed_exchange_is_a_readable_401():
    (status, body), _ = serve(FakeStore(), lambda c: sign_in(c, code="bad"))
    assert status == 401 and "sign-in didn't work" in body["error"]


def test_unknown_channel_becomes_practice():
    store = FakeStore()
    add_day(store)

    async def scenario(client):
        _, body = await sign_in(client, channel="999")
        r = await client.get("/api/today", headers=auth(body["token"]))
        return await r.json()

    today, _ = serve(store, scenario)
    assert today["mode"] == "practice" and len(today["sets"][0]["pairs"]) == 10


def test_today_returns_the_match_and_board():
    store = FakeStore()
    add_day(store)

    async def scenario(client):
        _, body = await sign_in(client)
        r = await client.get("/api/today", headers=auth(body["token"]))
        return await r.json()

    today, _ = serve(store, scenario)
    assert today["mode"] == "daily" and today["dayKey"] == "2026-10-22"
    assert today["channelName"] == "daily-hadith"
    assert today["subtitle"] == (
        "Names 49 to 58, including today's name, Al-Mubdi. Everyone in this server gets the same 10."
    )
    assert today["sets"][0]["pairs"][0]["leftAr"]
    assert today["myResult"] is None and today["board"] == []


def test_switched_off_channel_is_practice():
    store = FakeStore()
    add_day(store)
    store.channels[CID]["name_match_enabled"] = False

    async def scenario(client):
        _, body = await sign_in(client)
        return await (await client.get("/api/today", headers=auth(body["token"]))).json()

    today, _ = serve(store, scenario)
    assert today["mode"] == "practice"


def test_result_is_scored_on_the_server_saved_once_and_edits_the_card():
    store = FakeStore()
    add_day(store)
    guesses = [[52, 53]] + [[i, i] for i in range(49, 59)]

    async def scenario(client):
        _, body = await sign_in(client)
        h = auth(body["token"])
        payload = {"dayKey": "2026-10-22", "guesses": guesses, "durationMs": 65000}
        first = await (await client.post("/api/result", json=payload, headers=h)).json()
        again = await client.post(
            "/api/result", json=dict(payload, guesses=[[i, i] for i in range(49, 59)]), headers=h
        )
        return first, await again.json()

    (first, again), edits = serve(store, scenario)
    assert first["recorded"] is True and first["result"]["score"] == 8
    assert first["board"][0]["isMe"] is True
    assert again["recorded"] is False and again["result"]["score"] == 8
    assert store.days[(CID, "2026-10-22")]["played"] is True
    assert edits == [("2026-10-22", False)]


def test_impossible_run_is_refused():
    store = FakeStore()
    add_day(store)

    async def scenario(client):
        _, body = await sign_in(client)
        r = await client.post(
            "/api/result",
            json={"dayKey": "2026-10-22", "guesses": [[1, 1]], "durationMs": 5000},
            headers=auth(body["token"]),
        )
        return r.status, await r.json()

    (status, body), _ = serve(store, scenario)
    assert status == 400 and "couldn't be scored" in body["error"]
    assert store.results == {}


def test_closed_match_refuses_late_runs_after_the_grace_period():
    store = FakeStore()
    long_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    just_now = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    add_day(store, "2026-10-21", closed_at=long_ago)
    add_day(store, "2026-10-22", closed_at=just_now)
    run = [[i, i] for i in range(49, 59)]

    async def scenario(client):
        _, body = await sign_in(client)
        h = auth(body["token"])
        old = await client.post("/api/result", json={"dayKey": "2026-10-21", "guesses": run, "durationMs": 30000}, headers=h)
        late = await client.post("/api/result", json={"dayKey": "2026-10-22", "guesses": run, "durationMs": 30000}, headers=h)
        return old.status, late.status

    (old, late), edits = serve(store, scenario)
    assert old == 409 and late == 200
    assert edits == [("2026-10-22", True)]


def test_requests_without_a_token_are_refused():
    async def scenario(client):
        r = await client.get("/api/today")
        return r.status

    status, _ = serve(FakeStore(), scenario)
    assert status == 401


def test_name_match_channels_gate(monkeypatch):
    monkeypatch.setenv("NAME_MATCH_CHANNELS", "")
    assert not game_api.name_match_on({"channel_id": "1"})
    monkeypatch.setenv("NAME_MATCH_CHANNELS", "1, 2")
    assert game_api.name_match_on({"channel_id": "2"})
    assert not game_api.name_match_on({"channel_id": "3"})
    monkeypatch.setenv("NAME_MATCH_CHANNELS", "*")
    assert game_api.name_match_on({"channel_id": "3"})
    assert not game_api.name_match_on({"channel_id": "3", "name_match_enabled": False})
