"""The notice a server gets when the bot can't post its daily hadith.

alert_delivery_failure is called as an unbound function against a stub rather
than a real HadithBot: it only touches _record_warned, fetch_user and
logger, so there's no reason to stand up a discord.py client (or add an async
test runner) to exercise it.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import discord
import pytest

import bot as bot_module
from bot import HadithBot
from utils import CHANNEL_DELETED, delivery_failure_message, embed_links_message

alert = HadithBot.alert_delivery_failure


def http_error():
    """A closed-DMs / no-access error shaped the way discord.py raises it."""
    return discord.HTTPException(
        SimpleNamespace(status=403, reason="Forbidden"), "Cannot send messages"
    )


class FakeUser:
    def __init__(self, *, open_dms=True):
        self.open_dms = open_dms
        self.received = []

    async def send(self, content):
        if not self.open_dms:
            raise http_error()
        self.received.append(content)


class FakeChannel:
    def __init__(self, cid, name, *, postable=True, send_fails=False):
        self.id = cid
        self.name = name
        self.postable = postable
        self.send_fails = send_fails
        self.received = []

    def permissions_for(self, _me):
        return SimpleNamespace(
            view_channel=self.postable, send_messages=self.postable
        )

    async def send(self, content):
        if self.send_fails:
            raise http_error()
        self.received.append(content)


class FakeGuild:
    def __init__(self, channels, *, owner_id=7, system_channel=None):
        self.name = "FAMILY GAMERS"
        self.owner_id = owner_id
        self.me = object()
        self.text_channels = channels
        self.system_channel = system_channel


class FakeBot:
    _record_warned = HadithBot._record_warned
    warn_about_embed_links = HadithBot.warn_about_embed_links

    def __init__(self, owner=None):
        self.logger = logging.getLogger("test")
        self._owner = owner

    async def fetch_user(self, _uid):
        if self._owner is None:
            raise http_error()
        return self._owner


@pytest.fixture(autouse=True)
def saved_warnings(monkeypatch):
    """(channel id, field, warned) for every warning time the code saved."""
    calls = []
    monkeypatch.setattr(bot_module, "set_warned", lambda *a: calls.append(a))
    return calls


def row(channel_id="1550799445942345878", channel_name="akh", guild_id="99"):
    return {
        "channel_id": channel_id,
        "channel_name": channel_name,
        "guild_id": guild_id,
    }


# --- the message itself ------------------------------------------------------


def test_message_names_both_permissions_and_the_way_out():
    msg = delivery_failure_message("#akh")
    assert "#akh" in msg
    assert "View Channel" in msg and "Send Messages" in msg
    # An admin shouldn't have to ask how to check the fix, or how to opt out.
    assert "/bismillah diagnose" in msg
    assert "/bismillah stop" in msg


def test_message_spells_out_the_clicks():
    """Step 2 is the one that fixes a private channel: without adding the role
    there is nothing to toggle, so 'grant the permission' alone is a dead end."""
    msg = delivery_failure_message("#akh")
    assert "Edit Channel" in msg
    assert "Roles/Members" in msg
    # Same steps as the public guide, so the two can't drift apart silently.
    assert "hadithbot.app/send-daily-hadith-discord" in msg


def test_dm_names_the_server_and_in_channel_does_not():
    assert "FAMILY GAMERS" in delivery_failure_message("#akh", "FAMILY GAMERS")
    assert "FAMILY GAMERS" not in delivery_failure_message("#akh")


# --- who gets told -----------------------------------------------------------


def test_owner_is_told_first():
    owner = FakeUser()
    general = FakeChannel(2, "general")
    guild = FakeGuild([general])

    assert asyncio.run(alert(FakeBot(owner), guild, row())) is True
    assert len(owner.received) == 1
    assert "FAMILY GAMERS" in owner.received[0]
    # A DM reached someone, so nothing is posted publicly.
    assert general.received == []


def test_falls_back_to_a_channel_when_the_owner_has_dms_closed():
    owner = FakeUser(open_dms=False)
    general = FakeChannel(2, "general")
    guild = FakeGuild([general])

    assert asyncio.run(alert(FakeBot(owner), guild, row())) is True
    assert len(general.received) == 1


def test_system_channel_is_preferred_over_other_channels():
    system = FakeChannel(3, "welcome")
    general = FakeChannel(2, "general")
    guild = FakeGuild([general], system_channel=system)

    assert asyncio.run(alert(FakeBot(), guild, row())) is True
    assert len(system.received) == 1
    assert general.received == []


def test_never_posts_into_the_broken_channel_itself():
    broken = FakeChannel(1550799445942345878, "akh")
    other = FakeChannel(2, "general")
    guild = FakeGuild([broken, other])

    assert asyncio.run(alert(FakeBot(), guild, row())) is True
    assert broken.received == []
    assert len(other.received) == 1


def test_skips_channels_it_cannot_post_in():
    locked = FakeChannel(2, "staff-only", postable=False)
    open_one = FakeChannel(3, "general")
    guild = FakeGuild([locked, open_one])

    assert asyncio.run(alert(FakeBot(), guild, row())) is True
    assert locked.received == []
    assert len(open_one.received) == 1


def test_keeps_trying_channels_after_a_send_raises():
    flaky = FakeChannel(2, "general", send_fails=True)
    open_one = FakeChannel(3, "chat")
    guild = FakeGuild([flaky, open_one])

    assert asyncio.run(alert(FakeBot(), guild, row())) is True
    assert len(open_one.received) == 1


def test_gives_up_quietly_when_there_is_nobody_to_tell():
    locked = FakeChannel(2, "staff-only", postable=False)
    guild = FakeGuild([locked])

    assert asyncio.run(alert(FakeBot(), guild, row())) is False


def test_no_guild_is_not_an_error():
    assert asyncio.run(alert(FakeBot(), None, row())) is False


# --- how often ---------------------------------------------------------------


def test_only_warns_once_while_the_channel_stays_broken(saved_warnings):
    owner = FakeUser()
    bot = FakeBot(owner)
    guild = FakeGuild([FakeChannel(2, "general")])
    r = row()

    assert asyncio.run(alert(bot, guild, r)) is True
    assert saved_warnings == [(r["channel_id"], "warned_at", True)]
    # Every following evening hits the same failure and must stay silent.
    for _ in range(5):
        assert asyncio.run(alert(bot, guild, r)) is False
    assert len(owner.received) == 1


def test_a_restart_does_not_warn_again():
    """The time is read from the row, not from the bot's memory."""
    owner = FakeUser()
    guild = FakeGuild([FakeChannel(2, "general")])
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    assert asyncio.run(alert(FakeBot(owner), guild, row() | {"warned_at": yesterday})) is False
    assert owner.received == []


def test_warns_again_after_a_week():
    owner = FakeUser()
    guild = FakeGuild([FakeChannel(2, "general")])
    last_week = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()

    assert asyncio.run(alert(FakeBot(owner), guild, row() | {"warned_at": last_week})) is True


def test_a_successful_delivery_re_arms_the_warning():
    owner = FakeUser()
    bot = FakeBot(owner)
    guild = FakeGuild([FakeChannel(2, "general")])
    r = row()

    asyncio.run(alert(bot, guild, r))
    # What save_channel_state(mark_sent=True) does once the channel delivers again.
    r["warned_at"] = None

    assert asyncio.run(alert(bot, guild, r)) is True
    assert len(owner.received) == 2


def test_channels_are_tracked_separately():
    owner = FakeUser()
    bot = FakeBot(owner)
    guild = FakeGuild([FakeChannel(2, "general")])

    assert asyncio.run(alert(bot, guild, row(channel_id="111"))) is True
    assert asyncio.run(alert(bot, guild, row(channel_id="222"))) is True
    assert len(owner.received) == 2


def test_falls_back_to_a_mention_when_the_name_is_unknown():
    owner = FakeUser()
    guild = FakeGuild([])

    asyncio.run(alert(FakeBot(owner), guild, row(channel_name=None)))
    assert "<#1550799445942345878>" in owner.received[0]


# --- noticing the moment access is lost ---------------------------------------

on_update = HadithBot.on_guild_channel_update
on_delete = HadithBot.on_guild_channel_delete
configured_row = HadithBot._configured_row


def discord_error(cls, status):
    return cls(SimpleNamespace(status=status, reason=""), "")


class FakeGuildChannel:
    """A channel as the gateway hands it to us, with our own permissions on it."""

    def __init__(self, cid=1, name="reminders", *, can_send=True, guild=None):
        self.id = cid
        self.name = name
        self.can_send = can_send
        self.guild = guild or FakeGuild([])

    def permissions_for(self, _me):
        return SimpleNamespace(view_channel=True, send_messages=self.can_send)


class ListenerBot:
    """Stub self for the listeners: records alerts instead of sending them."""

    def __init__(self, *, row=None, fetch_error=None):
        self.logger = logging.getLogger("test")
        self._row = row
        self._fetch_error = fetch_error
        self.alerted = []

    def _configured_row(self, _channel_id):
        return self._row

    async def fetch_channel(self, _cid):
        if self._fetch_error:
            raise self._fetch_error
        return object()

    async def alert_delivery_failure(self, guild, channel_row):
        self.alerted.append((guild, channel_row))
        return True

    _channel_was_deleted = HadithBot._channel_was_deleted
    _mark_channel_deleted = HadithBot._mark_channel_deleted


@pytest.fixture
def stopped(monkeypatch):
    """(channel id, reason) for each channel the code under test stopped."""
    calls = []
    monkeypatch.setattr(bot_module, "stop_channel", lambda cid, reason: calls.append((cid, reason)))
    return calls


def test_losing_send_messages_warns_immediately():
    b = ListenerBot(row=row())
    before = FakeGuildChannel(can_send=True)
    after = FakeGuildChannel(can_send=False, guild=before.guild)

    asyncio.run(on_update(b, before, after))
    assert len(b.alerted) == 1


def test_no_warning_when_the_channel_is_not_set_up():
    b = ListenerBot(row=None)
    before = FakeGuildChannel(can_send=True)
    after = FakeGuildChannel(can_send=False, guild=before.guild)

    asyncio.run(on_update(b, before, after))
    assert b.alerted == []


def test_no_warning_for_unrelated_permission_edits():
    b = ListenerBot(row=row())
    before = FakeGuildChannel(can_send=True)
    after = FakeGuildChannel(can_send=True, guild=before.guild)

    asyncio.run(on_update(b, before, after))
    assert b.alerted == []


def test_regaining_permission_is_not_a_warning():
    b = ListenerBot(row=row())
    before = FakeGuildChannel(can_send=False)
    after = FakeGuildChannel(can_send=True, guild=before.guild)

    asyncio.run(on_update(b, before, after))
    assert b.alerted == []


def test_made_private_warns():
    """403 on the follow-up fetch: the channel exists, we just can't see it."""
    b = ListenerBot(row=row(), fetch_error=discord_error(discord.Forbidden, 403))

    asyncio.run(on_delete(b, FakeGuildChannel()))
    assert len(b.alerted) == 1


def test_a_deleted_channel_says_nothing_and_is_stopped(stopped):
    """404: they deleted it on purpose, so there is nothing to tell them."""
    b = ListenerBot(row=row(), fetch_error=discord_error(discord.NotFound, 404))

    asyncio.run(on_delete(b, FakeGuildChannel()))
    assert b.alerted == []
    assert stopped == [(row()["channel_id"], CHANNEL_DELETED)]


def test_made_private_is_not_stopped(stopped):
    b = ListenerBot(row=row(), fetch_error=discord_error(discord.Forbidden, 403))

    asyncio.run(on_delete(b, FakeGuildChannel()))
    assert stopped == []


def test_delete_event_we_can_still_fetch_is_ignored(stopped):
    b = ListenerBot(row=row())

    asyncio.run(on_delete(b, FakeGuildChannel()))
    assert b.alerted == []
    assert stopped == []


def test_only_a_404_counts_as_deleted():
    """The broadcast's check for channels deleted while the bot was offline."""
    gone = ListenerBot(fetch_error=discord_error(discord.NotFound, 404))
    hidden = ListenerBot(fetch_error=discord_error(discord.Forbidden, 403))
    outage = ListenerBot(fetch_error=discord_error(discord.HTTPException, 500))
    assert asyncio.run(gone._channel_was_deleted("1")) is True
    assert asyncio.run(hidden._channel_was_deleted("1")) is False
    assert asyncio.run(outage._channel_was_deleted("1")) is False
    assert asyncio.run(ListenerBot()._channel_was_deleted("1")) is False


def test_a_failed_stop_is_logged_not_raised(monkeypatch):
    def boom(_cid, _reason):
        raise RuntimeError("supabase down")

    monkeypatch.setattr(bot_module, "stop_channel", boom)
    ListenerBot()._mark_channel_deleted(row())


def test_delete_of_an_unconfigured_channel_is_ignored():
    b = ListenerBot(row=None, fetch_error=discord_error(discord.Forbidden, 403))

    asyncio.run(on_delete(b, FakeGuildChannel()))
    assert b.alerted == []


# --- which channels we care about --------------------------------------------


class RowBot:
    def __init__(self):
        self.logger = logging.getLogger("test")


def test_stopped_channels_are_not_watched(monkeypatch):
    stopped_row = row() | {"stopped_at": "2026-10-25T12:00:00Z", "stopped_reason": "stopped_by_admin"}
    monkeypatch.setattr(bot_module, "get_channel_state", lambda _c: stopped_row)
    assert configured_row(RowBot(), "1") is None


def test_channels_getting_messages_are_watched(monkeypatch):
    monkeypatch.setattr(bot_module, "get_channel_state", lambda _c: row() | {"stopped_at": None})
    assert configured_row(RowBot(), "1") is not None


def test_a_database_outage_does_not_crash_the_listener(monkeypatch):
    def boom(_c):
        raise RuntimeError("supabase down")

    monkeypatch.setattr(bot_module, "get_channel_state", boom)
    assert configured_row(RowBot(), "1") is None


def test_servers_the_bot_was_removed_from_are_left_alone(monkeypatch):
    """Their rows are kept deliberately (mark_guild_removed), but there is
    nobody to tell and no permission to fix."""
    monkeypatch.setattr(
        bot_module,
        "get_channel_state",
        lambda _c: row() | {"stopped_at": "2026-09-19T00:00:00Z", "stopped_reason": "bot_removed"},
    )
    assert configured_row(RowBot(), "1") is None


# --- the game card without Embed Links -----------------------------------------


def card_channel(guild):
    return SimpleNamespace(name="daily-hadith", guild=guild)


def test_embed_links_dm_goes_to_the_owner_once(saved_warnings):
    owner = FakeUser()
    bot = FakeBot(owner)
    channel = card_channel(FakeGuild([]))
    r = row()

    assert asyncio.run(bot.warn_about_embed_links(channel, r)) is True
    assert asyncio.run(bot.warn_about_embed_links(channel, r)) is False
    assert owner.received == [embed_links_message("#daily-hadith", "FAMILY GAMERS")]
    assert saved_warnings == [(r["channel_id"], "embed_warned_at", True)]


def test_embed_links_dm_never_posts_in_a_channel(saved_warnings):
    """Closed DMs: the card in the channel already carries the note."""
    general = FakeChannel(2, "general")
    bot = FakeBot(None)

    assert asyncio.run(bot.warn_about_embed_links(card_channel(FakeGuild([general])), row())) is False
    assert general.received == []
    assert saved_warnings == []


def test_embed_links_message_has_no_em_dashes():
    text = embed_links_message("#daily-hadith", "Server")
    assert "—" not in text and "Embed Links" in text
