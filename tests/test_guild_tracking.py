"""Only the production bot records servers as removed or back.

The dev bot runs against the same database, so its view of which servers it
is in must never reach removed_at.
"""

import asyncio
import logging
from types import SimpleNamespace

import pytest

import bot as bot_module
from bot import PRODUCTION_BOT_ID, HadithBot

DEV_BOT_ID = 1


class GuildBot:
    _is_production = HadithBot._is_production
    reconcile_guilds = HadithBot.reconcile_guilds
    on_guild_remove = HadithBot.on_guild_remove
    on_guild_join = HadithBot.on_guild_join

    def __init__(self, user_id, guild_ids=()):
        self.user = SimpleNamespace(id=user_id)
        self.guilds = [SimpleNamespace(id=int(g)) for g in guild_ids]
        self.logger = logging.getLogger("test")


@pytest.fixture
def writes(monkeypatch):
    calls = []
    monkeypatch.setattr(bot_module, "get_known_guild_ids", lambda: {"10", "20"})
    monkeypatch.setattr(bot_module, "mark_guild_removed", lambda g: calls.append(("removed", g)) or 1)
    monkeypatch.setattr(bot_module, "mark_guild_present", lambda g: calls.append(("present", g)) or 1)
    return calls


GUILD = SimpleNamespace(id=10, name="Server")


def test_production_reconcile_flags_and_restores(writes):
    asyncio.run(GuildBot(PRODUCTION_BOT_ID, ["20"]).reconcile_guilds())
    assert sorted(writes) == [("present", "20"), ("removed", "10")]


def test_dev_bot_reconcile_writes_nothing(writes):
    asyncio.run(GuildBot(DEV_BOT_ID, ["20"]).reconcile_guilds())
    assert writes == []


@pytest.mark.parametrize("handler", ["on_guild_remove", "on_guild_join"])
def test_dev_bot_join_and_remove_write_nothing(writes, handler):
    asyncio.run(getattr(GuildBot(DEV_BOT_ID), handler)(GUILD))
    assert writes == []


def test_production_join_and_remove_write(writes):
    b = GuildBot(PRODUCTION_BOT_ID)
    asyncio.run(b.on_guild_remove(GUILD))
    asyncio.run(b.on_guild_join(GUILD))
    assert writes == [("removed", "10"), ("present", "10")]


def test_not_logged_in_counts_as_not_production(writes):
    b = GuildBot(PRODUCTION_BOT_ID, ["20"])
    b.user = None
    asyncio.run(b.reconcile_guilds())
    assert writes == []
