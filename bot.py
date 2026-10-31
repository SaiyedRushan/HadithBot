from datetime import datetime, time, timezone
import aiofiles
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
import json
import random
import logging
from typing import List, Optional
from zoneinfo import ZoneInfo
from db import (
    find_valid_hadith_position,
    get_all_channels,
    get_books,
    get_chapters,
    get_channels,
    get_channel_state,
    get_hadith_in_same_chapter_and_book,
    get_flags_for_hadith,
    get_known_guild_ids,
    get_next_hadiths,
    get_open_flags,
    get_random_hadith,
    mark_guild_present,
    mark_guild_removed,
    resolve_hadith_flags,
    save_channel_state,
    set_warned,
    stop_channel,
)
from views import (
    ExplainHadithButton,
    FlagHadithButton,
    PlayNameMatchButton,
    build_ayah_view,
    build_hadith_view,
    build_name_match_view,
)
import db
import name_match
from quran import Ayah, DailyAyah, ayah_on, format_ayah_messages, greeting
from command_sync import sync_commands
from game_api import card_message, edit_card, name_match_on
from utils import (
    CHANNEL_DELETED,
    STOPPED_BY_ADMIN,
    Name,
    compose_flag_reply,
    ABSOLUTE_MAX_PER_DAY,
    channel_max,
    daily_count,
    delivery_failure_message,
    embed_links_message,
    getHadithFormattedMessage,
    getNameFormattedMessage,
    load_custom_limits,
    resolve_start_position,
    setup_reply,
    stopped_text,
    update_for,
    warned_recently,
    with_divider,
)

# Tail of the /bismillah books and /bismillah chapters replies. Both lists run
# to several messages in Discord and can't be searched; the page holds the same
# ids in one place, with the hadith counts and number ranges alongside them.
BOOKS_PAGE_HINT = "\n-# The full list, searchable, is at <https://hadithbot.app/books>"

# The production bot's user id (the client_id in the site's invite links).
# Local development runs a different bot against the same database, and its
# server list says nothing about where HadithBot is, so only this bot may
# record a server as removed or back.
PRODUCTION_BOT_ID = 1285370394282295359


class HadithBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

        self.names: List[Name] = []
        # Today's verse of the Quran, fetched once and shared by every channel.
        self.daily_ayah = DailyAyah()
        self.logger = logging.getLogger("HadithBot")

        # Setup error handling
        self.setup_error_handlers()

    async def setup_hook(self):
        """Initialize bot data and sync commands"""
        await self.load_data()
        # Registered before anything is sent so button clicks on messages from a
        # previous run are still routed to a handler after a restart.
        self.add_dynamic_items(ExplainHadithButton, FlagHadithButton, PlayNameMatchButton)
        # Not tree.sync(): that would delete the Activity's Entry Point command,
        # which Discord refuses, and the bot would fail to start. See command_sync.
        await sync_commands(self)
        self.send_daily_message.start()

    async def load_data(self):
        """Load messages and names from local storage"""
        try:
            # Read and parse 99names.json
            async with aiofiles.open("data/99names.json", mode="r") as file:
                names_data = json.loads(await file.read())
                self.names = [Name(**name) for name in names_data]

        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            raise

    def setup_error_handlers(self):
        @self.event
        async def on_error(event, *args, **kwargs):
            self.logger.error(f"Error in {event}", exc_info=True)

        @self.tree.error
        async def on_command_error(
            interaction: discord.Interaction, error: app_commands.AppCommandError
        ):
            if isinstance(error, app_commands.CommandOnCooldown):
                message = f"Please wait {error.retry_after:.2f} seconds before using this command again."
            elif isinstance(error, app_commands.MissingPermissions):
                message = (
                    "You need the **Manage Channels** permission to use this command."
                )
            elif isinstance(getattr(error, "original", None), discord.Forbidden):
                message = (
                    "I don't have permission to post in this channel. "
                    "Please grant me **View Channel** and **Send Messages** here."
                )
            else:
                self.logger.error(f"Command error: {error}", exc_info=True)
                message = "An error occurred while processing your command. Please try again later."

            # Commands defer() before doing work, so the interaction is usually
            # already responded to by the time an error reaches here -- use
            # followup.send() in that case to avoid InteractionResponded.
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(message, ephemeral=True)
                else:
                    await interaction.response.send_message(message, ephemeral=True)
            except discord.HTTPException:
                self.logger.error(
                    "Failed to deliver error message to user", exc_info=True
                )

    @tasks.loop(time=time(hour=18, tzinfo=ZoneInfo("America/Toronto")))
    async def send_daily_message(self):
        """Loops through the active channels and sends daily messages"""
        await self.run_daily_broadcast()

    async def run_daily_broadcast(self, only_channel_id: Optional[str] = None) -> int:
        """The daily broadcast itself, callable outside the 6pm schedule.

        Split out of send_daily_message so /bismillah send-now exercises this
        exact code path rather than a copy that can drift from it. Returns the
        number of channels delivered to; only_channel_id restricts it to one,
        which is what the command uses so a test can't spam every server."""
        try:
            channels = get_channels()
        except Exception as e:
            self.logger.error(f"Failed to fetch active channels: {e}")
            return 0

        if only_channel_id is not None:
            channels = [
                c for c in channels if str(c["channel_id"]) == str(only_channel_id)
            ]

        delivered = 0
        custom_limits = load_custom_limits()
        today = datetime.now(ZoneInfo("America/Toronto")).date()
        # Today's update message (updates/<date>.md), if any, goes first.
        update = update_for(today)
        for channel_row in channels:
            channel_id = channel_row["channel_id"]
            # Isolate each channel so one failure (e.g. missing permissions)
            # doesn't stop the broadcast to the remaining channels.
            channel = None
            try:
                last_hadith_no = channel_row["last_hadith_no"]
                last_name_no = channel_row["last_name_no"]
                last_book_no = channel_row["last_book_id"]
                last_chapter_no = channel_row["last_chapter_id"]
                # Per-channel daily counts, held to the cap (3, unless the
                # channel was given more on request) even for rows saved back
                # when up to 10 was allowed.
                cap = channel_max(channel_id, custom_limits)
                hadiths_per_day = daily_count(channel_row.get("hadiths_per_day"), cap)
                names_per_day = daily_count(channel_row.get("names_per_day"), cap)

                channel = self.get_channel(int(channel_id))
                if not channel:
                    # Servers the bot was removed from are already filtered out
                    # by get_channels(), so reaching here means the bot is still
                    # in the server but can't see the channel: deleted, or View
                    # Channel was revoked. A deletion while the bot was offline
                    # never fires on_guild_channel_delete, so check here too.
                    if await self._channel_was_deleted(channel_id):
                        self._mark_channel_deleted(channel_row)
                        continue
                    self.logger.error(
                        f"Channel {channel_id} not found in "
                        f"{channel_row.get('guild_name') or 'unknown server'} -- "
                        "deleted, or the bot lost View Channel"
                    )
                    guild_id = channel_row.get("guild_id")
                    if guild_id:
                        await self.alert_delivery_failure(
                            self.get_guild(int(guild_id)), channel_row
                        )
                    continue

                # The book/chapter we resumed from (before position resolution).
                # Used to detect when today's batch moves into a new book/chapter
                # -- including a day-boundary roll-over -- so we can announce it.
                prev_book_no = last_book_no
                prev_chapter_no = last_chapter_no

                last_hadith_no, last_book_no, last_chapter_no = (
                    find_valid_hadith_position(
                        last_hadith_no, last_book_no, last_chapter_no
                    )
                )

                # Fetched before the greeting, which only mentions the verse
                # when there is one to send.
                ayah = await self.daily_ayah.for_day(today) if ayah_on(channel_row) else None

                if update:
                    await channel.send(
                        update, allowed_mentions=discord.AllowedMentions.none()
                    )
                await channel.send(greeting(ayah is not None))
                if ayah is not None:
                    # Its own try, like the name match: a verse that fails to
                    # post must not stop the hadith.
                    try:
                        await self.send_ayah(channel, ayah)
                    except Exception:
                        self.logger.error(
                            f"Failed to post verse {ayah.key} in {channel_id}",
                            exc_info=True,
                        )
                # get name and send message
                names = self.get_names(last_name_no, names_per_day)
                current_name_index = self.get_next_index(
                    last_name_no, len(self.names), names_per_day
                )
                await self.send_formatted_name(
                    channel, names, after_verse=ayah is not None
                )

                # get today's batch starting at the current position; this crosses
                # chapter/book boundaries so the full daily count is sent even when
                # the current chapter has fewer hadiths left than hadiths_per_day
                hadith = get_next_hadiths(
                    last_hadith_no, last_book_no, last_chapter_no, hadiths_per_day
                )

                if hadith:
                    for h in hadith:
                        # Announce whenever a hadith opens a book/chapter different
                        # from the previous one sent (a new book implies a new
                        # chapter, so only send one banner). A banner carries the
                        # divider itself, so the line sits above it and not
                        # between it and the hadith it introduces.
                        announced = True
                        if h["book_id"] != prev_book_no:
                            await self.send_new_book_message(channel, h)
                        elif h["chapter_id"] != prev_chapter_no:
                            await self.send_new_chapter_message(channel, h)
                        else:
                            announced = False
                        prev_book_no = h["book_id"]
                        prev_chapter_no = h["chapter_id"]

                        await self.send_formatted_hadith(
                            channel, h, divider=not announced
                        )

                    # The last hadith sent may be in a later chapter/book than we
                    # started; advance the saved position past it so tomorrow
                    # continues from the right spot.
                    last = hadith[-1]
                    last_book_no = last["book_id"]
                    last_chapter_no = last["chapter_id"]
                    next_hadith_no = last["id_in_book"] + 1

                    guild = getattr(channel, "guild", None)
                    save_channel_state(
                        channel_id,
                        next_hadith_no,
                        current_name_index,
                        last_book_no,
                        last_chapter_no,
                        channel_name=getattr(channel, "name", None),
                        guild_id=str(guild.id) if guild else None,
                        guild_name=guild.name if guild else None,
                        guild_member_count=guild.member_count if guild else None,
                        mark_sent=True,
                    )

                    delivered += 1

                    if name_match_on(channel_row) and names:
                        # Its own try: the hadith is already out and saved, so a
                        # failed card must not count as a failed delivery.
                        try:
                            await self.post_name_match(channel, names, channel_row)
                        except Exception:
                            self.logger.error(
                                f"Failed to post the name match in {channel_id}",
                                exc_info=True,
                            )
                    self.logger.info(
                        f"Successfully sent hadith up to book {last_book_no}, chapter {last_chapter_no}, hadith {last['id_in_book']}"
                    )
                else:
                    self.logger.error(
                        f"No hadith data returned for book {last_book_no}, chapter {last_chapter_no}, hadith {last_hadith_no}"
                    )
            except discord.Forbidden as e:
                self.logger.error(
                    f"Failed to send daily message to channel {channel_id}: {e}",
                    exc_info=True,
                )
                await self.alert_delivery_failure(
                    getattr(channel, "guild", None), channel_row
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to send daily message to channel {channel_id}: {e}",
                    exc_info=True,
                )
        return delivered

    def _configured_row(self, channel_id):
        """The stored row for a channel, but only if it still gets messages.

        Returns None for channels nobody asked us to post in, so a permission
        change in an unrelated channel costs one lookup and nothing else.
        """
        try:
            row = get_channel_state(str(channel_id))
        except Exception as e:
            self.logger.error(f"Couldn't look up channel {channel_id}: {e}")
            return None
        # A stopped channel keeps its row, but whatever the reason (removed
        # from the server, deleted, stopped by an admin) there is nothing to
        # warn anyone about.
        if row is None or row.get("stopped_at"):
            return None
        return row

    async def on_guild_channel_update(self, before, after):
        """Warn as soon as we lose the ability to post, not at 6pm.

        Waiting for the next broadcast means an admin who breaks the channel at
        noon hears nothing until the evening, by which point they've forgotten
        what they changed. This catches the case where we keep View Channel but
        lose Send Messages -- losing View Channel removes the channel from our
        cache entirely and arrives as a delete instead.
        """
        me = getattr(after.guild, "me", None)
        if me is None or not hasattr(after, "permissions_for"):
            return

        could_send = before.permissions_for(me).send_messages
        can_send = after.permissions_for(me).send_messages
        if could_send and not can_send:
            row = self._configured_row(after.id)
            if row is not None:
                self.logger.info(f"Lost Send Messages in #{after.name}")
                await self.alert_delivery_failure(after.guild, row)

    async def on_guild_channel_delete(self, channel):
        """A channel we post in vanished from our view.

        Discord sends this both when a channel is deleted and when we lose
        View Channel on it, which is what making a channel private does to us.
        Only the second is worth a message -- someone who deleted a channel
        knows they deleted it -- so ask the API which happened: 403 means it
        still exists and we can't see it, 404 means it's really gone.
        """
        row = self._configured_row(channel.id)
        if row is None:
            return

        try:
            await self.fetch_channel(channel.id)
            return  # Still reachable, so nothing was actually lost.
        except discord.Forbidden:
            self.logger.info(f"Lost access to #{channel.name}")
            await self.alert_delivery_failure(channel.guild, row)
        except discord.NotFound:
            # Deliberately silent: they deleted it, they know.
            self._mark_channel_deleted(row)
        except discord.HTTPException as e:
            self.logger.error(f"Couldn't tell why #{channel.name} went away: {e}")

    async def _channel_was_deleted(self, channel_id) -> bool:
        """True only when Discord says the channel is gone (404). A 403 means
        it exists and we can't see it, which is worth telling someone about."""
        try:
            await self.fetch_channel(int(channel_id))
        except discord.NotFound:
            return True
        except discord.HTTPException:
            pass
        return False

    def _mark_channel_deleted(self, row) -> None:
        """Stop a deleted channel, keeping its row.

        Left getting messages it fails every broadcast and shows on the stale
        check.
        """
        channel_id = str(row["channel_id"])
        label = f"#{row.get('channel_name') or channel_id}"
        try:
            stop_channel(channel_id, CHANNEL_DELETED)
            self.logger.info(f"{label} was deleted; stopped its daily message")
        except Exception as e:
            self.logger.error(f"Couldn't mark deleted channel {label} as stopped: {e}")

    def _record_warned(self, channel_row, field: str) -> None:
        """Save when the owner was told, so a restart doesn't tell them again.
        Also set on the row itself, for a caller that reuses it."""
        try:
            set_warned(str(channel_row["channel_id"]), field, True)
        except Exception as e:
            self.logger.error(f"Couldn't save {field} for {channel_row['channel_id']}: {e}")
        channel_row[field] = datetime.now(timezone.utc).isoformat()

    async def warn_about_embed_links(self, channel, channel_row) -> bool:
        """DM the owner, once a week, while the game card has to go out as text.

        The card carries the same note, but the person who can fix it may not
        read that channel. No fallback to posting in a channel, as the alert
        above does: the card is already posted in one.
        """
        if warned_recently(channel_row.get("embed_warned_at")):
            return False
        guild = getattr(channel, "guild", None)
        if guild is None or not guild.owner_id:
            return False
        try:
            owner = await self.fetch_user(guild.owner_id)
            await owner.send(embed_links_message(f"#{channel.name}", guild.name))
        except discord.HTTPException as e:
            self.logger.info(f"Couldn't DM {guild.name}'s owner about Embed Links: {e}")
            return False
        self._record_warned(channel_row, "embed_warned_at")
        self.logger.info(f"Told {guild.name}'s owner about Embed Links in #{channel.name}")
        return True

    async def alert_delivery_failure(self, guild, channel_row) -> bool:
        """Tell someone in the server that today's hadith couldn't be posted.

        Losing access to a channel is silent from the server's side: the bot
        logs a 403 and the hadiths simply stop arriving, so nobody knows there
        is anything to fix. Try the owner by DM first -- they can always
        restore the permission and a DM doesn't put the problem in front of
        the whole server -- then fall back to any channel we can still post in.

        Sends at most once a week per channel (warned_at), until delivery
        succeeds again. Returns True if the notice reached anyone.
        """
        if guild is None:
            return False

        channel_id = str(channel_row["channel_id"])
        if warned_recently(channel_row.get("warned_at")):
            return False

        name = channel_row.get("channel_name")
        label = f"#{name}" if name else f"<#{channel_id}>"

        # The owner is the one person we can always identify without the
        # members intent, and the one person who can always fix this.
        if guild.owner_id:
            try:
                owner = await self.fetch_user(guild.owner_id)
                await owner.send(delivery_failure_message(label, guild.name))
                self._record_warned(channel_row, "warned_at")
                self.logger.info(f"Told {guild.name}'s owner about {label}")
                return True
            except discord.HTTPException:
                # Closed DMs are common; fall through to a channel.
                pass

        me = guild.me
        if me is None:
            return False

        # System channel first (it already carries Discord's own server
        # notices), then anything else we can post in.
        candidates = []
        if guild.system_channel is not None:
            candidates.append(guild.system_channel)
        candidates.extend(guild.text_channels)

        seen = {int(channel_id)}
        for target in candidates:
            if target.id in seen:
                continue
            seen.add(target.id)
            perms = target.permissions_for(me)
            if not (perms.view_channel and perms.send_messages):
                continue
            try:
                await target.send(delivery_failure_message(label))
                self._record_warned(channel_row, "warned_at")
                self.logger.info(f"Posted the {label} failure notice in #{target.name}")
                return True
            except discord.HTTPException:
                continue

        self.logger.error(
            f"Couldn't reach anyone in {guild.name} about {label}: "
            "the owner's DMs are closed and no channel is postable"
        )
        return False

    @send_daily_message.before_loop
    async def before_daily_message(self):
        """Wait for the bot to be ready before starting the task"""
        await self.wait_until_ready()
        await self.reconcile_guilds()
        self.logger.info("\nDaily message task is ready to start\n")

    def _is_production(self) -> bool:
        return self.user is not None and self.user.id == PRODUCTION_BOT_ID

    async def on_guild_remove(self, guild: discord.Guild):
        """Kicked, banned, or the server was deleted.

        The rows are kept -- see mark_guild_removed -- so re-adding the bot
        resumes the server's reading position rather than starting over.
        """
        if not self._is_production():
            return
        try:
            flagged = mark_guild_removed(str(guild.id))
        except Exception:
            self.logger.error(
                f"Removed from guild {guild.id} ({guild.name}) but couldn't flag "
                "its channels; the startup reconcile will retry",
                exc_info=True,
            )
            return
        if flagged:
            self.logger.info(
                f"Removed from {guild.name} ({guild.id}) -- flagged {flagged} "
                "channel(s) as removed, rows kept"
            )

    async def on_guild_join(self, guild: discord.Guild):
        """Added to a server. If we'd been in it before, pick its channels back up."""
        if not self._is_production():
            return
        try:
            restored = mark_guild_present(str(guild.id))
        except Exception:
            self.logger.error(
                f"Joined guild {guild.id} ({guild.name}) but couldn't clear its "
                "removed flag; the startup reconcile will retry",
                exc_info=True,
            )
            return
        if restored:
            self.logger.info(
                f"Re-added to {guild.name} ({guild.id}) -- resuming {restored} "
                "channel(s) from where they left off"
            )

    async def reconcile_guilds(self):
        """Match the stored guilds against the ones Discord just handed us.

        on_guild_remove only fires while the bot is connected, so a kick during
        a restart or an outage is missed entirely -- which is how a server the
        bot had been out of for two weeks was still being counted on the site
        and still logging a failed delivery every evening. This runs once per
        startup and closes that gap in both directions.

        Production only: the dev bot shares the database but is in a handful
        of test servers, so from its point of view every real server has
        removed it, and the 6 PM broadcast would skip them all.
        """
        if not self._is_production():
            self.logger.info("Skipping guild reconcile: not the production bot")
            return
        live = {str(g.id) for g in self.guilds}
        # A reconcile against an empty cache would flag every server as removed.
        # That should be impossible after wait_until_ready(), so treat it as a
        # broken connection rather than as the bot having been kicked from
        # everywhere at once.
        if not live:
            self.logger.warning(
                "Skipping guild reconcile: Discord reported no guilds, which is "
                "more likely a connection problem than a removal from every server"
            )
            return

        try:
            known = get_known_guild_ids()
            for guild_id in known - live:
                if mark_guild_removed(guild_id):
                    self.logger.info(
                        f"Reconcile: no longer in guild {guild_id} -- flagged its "
                        "channels as removed, rows kept"
                    )
            for guild_id in known & live:
                if mark_guild_present(guild_id):
                    self.logger.info(
                        f"Reconcile: back in guild {guild_id} -- resuming its channels"
                    )
        except Exception:
            self.logger.error("Guild reconcile failed", exc_info=True)

    async def post_name_match(
        self, channel: discord.TextChannel, names: List[Name], channel_row: dict
    ):
        """Close the channel's earlier match cards, then post today's.

        Closing happens here rather than on a timer: every channel's day ends
        when its next batch goes out, so the broadcast is the one place that
        knows a match is over.
        """
        channel_id = str(channel.id)
        today = name_match.day_key()
        for old in db.get_open_game_days_before(channel_id, today):
            await edit_card(self, db, old, final=True)
            db.close_game_day(channel_id, str(old["day_key"]))

        numbers = name_match.pick_names(names[-1].number, len(self.names))
        items = name_match.build_items(self.names, numbers, [n.number for n in names])
        guild = getattr(channel, "guild", None)
        day = db.upsert_game_day(channel_id, today, str(guild.id) if guild else None, items)
        day["day_key"] = str(day["day_key"])
        embed = name_match.card_embed(
            day,
            db.get_game_results(channel_id, today),
            played_keys=db.get_played_day_keys(channel_id),
            others={g: db.get_game_results(channel_id, today, g) for g in name_match.GAME_ORDER[1:]},
        )
        card = card_message(channel, embed)
        message = await channel.send(**card, view=build_name_match_view())
        db.set_game_day_message(channel_id, today, str(message.id))
        if card["embed"] is None:
            await self.warn_about_embed_links(channel, channel_row)
        elif channel_row.get("embed_warned_at"):
            set_warned(channel_id, "embed_warned_at", False)

    def get_names(self, number: int, count: int = 1) -> Optional[List[Name]]:
        """Get name by number with validation"""
        if 1 <= number <= len(self.names):
            return self.names[number - 1 : number + count - 1]
        return None

    @staticmethod
    def get_next_index(current: int, max_value: int, increment: int = 1) -> int:
        """Get next index with wraparound"""
        return (current + increment) if (current + increment < max_value) else 1

    async def send_new_book_message(self, channel: discord.TextChannel, hadith: dict):
        """Announce that the daily readings have moved into a new book."""
        book = (hadith.get("books_metadata") or {}).get("english_title") or "a new book"
        chapter = (hadith.get("chapters") or {}).get("english") or ""
        message = f"# 📖 We are now starting a new book: {book}\n"
        if chapter:
            message += f"### Beginning with Chapter: {chapter}\n"
        await channel.send(with_divider(message))

    async def send_new_chapter_message(
        self, channel: discord.TextChannel, hadith: dict
    ):
        """Announce that the daily readings have moved into a new chapter."""
        chapter = (hadith.get("chapters") or {}).get("english") or "a new chapter"
        await channel.send(
            with_divider(f"# 📖 We are now starting a new chapter: {chapter}\n")
        )

    async def send_formatted_hadith(
        self, channel: discord.TextChannel, hadith: dict, divider: bool = False
    ):
        """Send formatted hadith message, with the divider above it if asked."""
        if not hadith:
            return
        formatted_messages = getHadithFormattedMessage(hadith)
        if divider:
            formatted_messages[0] = with_divider(formatted_messages[0])
        # Attach the link button to the last chunk so it sits under the full hadith.
        view = build_hadith_view(hadith)
        last_index = len(formatted_messages) - 1
        for i, message in enumerate(formatted_messages):
            if i == last_index and view is not None:
                await channel.send(message, view=view)
            else:
                await channel.send(message)

    async def send_ayah(self, channel: discord.TextChannel, ayah: Ayah):
        """Send the verse of the day, with its tafsir and Quran.com links under it."""
        messages = format_ayah_messages(ayah)
        for i, message in enumerate(messages):
            if i == len(messages) - 1:
                await channel.send(message, view=build_ayah_view(ayah))
            else:
                await channel.send(message)

    async def send_formatted_name(
        self,
        channel: discord.TextChannel,
        names: List[Name],
        after_verse: bool = False,
    ):
        """Send formatted name messages, with a divider between each name.

        The first name only gets one when the verse came before it.
        """
        if not names:
            return
        for i, name in enumerate(names):
            formatted_message = getNameFormattedMessage(name)
            await channel.send(
                with_divider(formatted_message) if i or after_verse else formatted_message
            )

    async def reply_formatted_hadith(
        self, interaction: discord.Interaction, hadith: dict
    ):
        """Send a hadith privately (ephemeral) to the command invoker.

        The interaction must already be deferred with ephemeral=True.
        """
        if not hadith:
            return
        formatted_messages = getHadithFormattedMessage(hadith)
        # Attach the link button to the last chunk so it sits under the full hadith.
        view = build_hadith_view(hadith)
        last_index = len(formatted_messages) - 1
        for i, message in enumerate(formatted_messages):
            if i == last_index and view is not None:
                await interaction.followup.send(message, view=view, ephemeral=True)
            else:
                await interaction.followup.send(message, ephemeral=True)

    async def reply_formatted_name(
        self, interaction: discord.Interaction, names: List[Name]
    ):
        """Send name(s) privately (ephemeral) to the command invoker.

        The interaction must already be deferred with ephemeral=True.
        """
        if not names:
            return
        for i, name in enumerate(names):
            message = getNameFormattedMessage(name)
            await interaction.followup.send(
                with_divider(message) if i else message, ephemeral=True
            )


# Command group for better organization
@app_commands.guild_only()
class HadithCommands(app_commands.Group):
    def __init__(self, bot: HadithBot):
        super().__init__(name="bismillah")
        self.bot = bot

    @app_commands.command(name="random")
    async def random(self, interaction: discord.Interaction):
        # Ephemeral so the result is visible only to the member who ran it.
        await interaction.response.defer(ephemeral=True)
        hadith = get_random_hadith()
        if not hadith:
            await interaction.followup.send(
                "Couldn't fetch a hadith right now. Please try again.",
                ephemeral=True,
            )
            return
        await self.bot.reply_formatted_hadith(interaction, hadith)

    @app_commands.command(name="specific")
    @app_commands.describe(book_no="The book id of the hadith")
    @app_commands.describe(chapter_no="The chapter id of the hadith")
    @app_commands.describe(hadith_no="The hadith id of the hadith")
    async def specific(
        self,
        interaction: discord.Interaction,
        book_no: int,
        chapter_no: int,
        hadith_no: int,
    ):
        await interaction.response.defer(ephemeral=True)
        hadith = get_hadith_in_same_chapter_and_book(hadith_no, book_no, chapter_no)
        if not hadith:
            await interaction.followup.send(
                "No hadith found for that book, chapter, and hadith combination.",
                ephemeral=True,
            )
            return
        await self.bot.reply_formatted_hadith(interaction, hadith[0])

    async def _send_names(
        self,
        interaction: discord.Interaction,
        names: Optional[List[Name]],
    ):
        """Validate the requested names, then send them privately to the invoker."""
        await interaction.response.defer(ephemeral=True)
        if not names:
            await interaction.followup.send(
                f"Invalid name number. Please choose between 1 and {len(self.bot.names)}",
                ephemeral=True,
            )
            return
        await self.bot.reply_formatted_name(interaction, names)

    @app_commands.command(name="random_name")
    async def random_name(self, interaction: discord.Interaction):
        names = self.bot.get_names(random.randint(1, len(self.bot.names)), 1)
        await self._send_names(interaction, names)

    @app_commands.command(name="specific_names")
    @app_commands.describe(number="The starting number of the names")
    async def specific_names(self, interaction: discord.Interaction, number: int):
        names = self.bot.get_names(number, 3)
        await self._send_names(interaction, names)

    @app_commands.command(name="specific_name")
    @app_commands.describe(number="The number of the name")
    async def specific_name(self, interaction: discord.Interaction, number: int):
        names = self.bot.get_names(number, 1)
        await self._send_names(interaction, names)

    @app_commands.command(name="setup")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(
        channel="Channel to send daily messages to (defaults to this channel)",
        hadiths_per_day="Hadiths a day, 1 to 3. We recommend 1. Blank keeps the current number.",
        names_per_day="Names of Allah a day, 1 to 3. We recommend 1. Blank keeps the current number.",
        start_book_id="Book id to start from — see /bismillah books (blank keeps current, or starts at the beginning)",
        start_chapter_id="Chapter id to start from — see /bismillah chapters (blank keeps current)",
        start_hadith_id="Hadith id to start from (blank uses the chapter's first hadith, or keeps current)",
        start_name="Name number to start from (blank keeps current)",
        name_match="Post a daily game after the hadith: match 10 names of Allah to their meanings. Blank keeps the current setting.",
        quran_verse="Start each day's message with a verse of the Quran. On by default. Blank keeps the current setting.",
    )
    async def setup(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        hadiths_per_day: Optional[app_commands.Range[int, 1, ABSOLUTE_MAX_PER_DAY]] = None,
        names_per_day: Optional[app_commands.Range[int, 1, ABSOLUTE_MAX_PER_DAY]] = None,
        start_book_id: Optional[int] = None,
        start_chapter_id: Optional[int] = None,
        start_hadith_id: Optional[int] = None,
        start_name: Optional[int] = None,
        name_match: Optional[bool] = None,
        quran_verse: Optional[bool] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        target = channel or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.followup.send(
                "Please pick a text channel (or run this inside one).",
                ephemeral=True,
            )
            return

        # Interaction replies use the interaction token, not channel permissions,
        # so setup can otherwise report success for a channel the bot can never
        # post in -- the failure only shows up as a missing message at 6pm.
        # Check up front and tell the admin while they're still here to fix it.
        me = target.guild.me
        if me is not None:
            perms = target.permissions_for(me)
            missing = [
                name
                for name, ok in (
                    ("View Channel", perms.view_channel),
                    ("Send Messages", perms.send_messages),
                )
                if not ok
            ]
            if missing:
                await interaction.followup.send(
                    f"I can't post in {target.mention} — missing "
                    f"{', '.join(f'**{m}**' for m in missing)}.\n"
                    "Grant those in the channel's permission settings and run "
                    "`/bismillah setup` again. Nothing has been saved.",
                    ephemeral=True,
                )
                return

        # Re-running setup edits the existing config. Any field left blank keeps
        # its current value (or falls back to a default for a brand-new channel),
        # so changing the daily counts no longer resets a channel's progress.
        existing = get_channel_state(str(target.id))

        def pick(value, key, default):
            if value is not None:
                return value
            if existing is not None:
                return existing.get(key, default)
            return default

        # Discord lets anyone type up to 10 (the Range above) so that channels
        # given a higher limit on request can use it; everyone else gets 3.
        cap = channel_max(target.id)
        if max(hadiths_per_day or 0, names_per_day or 0) > cap:
            await interaction.followup.send(
                f"You can choose 1 to {cap} hadiths and 1 to {cap} names a day. "
                f"To go higher in {target.mention}, email support@hadithbot.app "
                "with your server's name. Nothing has been saved.",
                ephemeral=True,
            )
            return
        # daily_count also brings a kept value from before the cap down to it.
        hpd = daily_count(pick(hadiths_per_day, "hadiths_per_day", None), cap)
        npd = daily_count(pick(names_per_day, "names_per_day", None), cap)

        # Book/chapter/hadith are resolved together so that changing the book or
        # chapter (without naming a hadith) starts at that chapter's first hadith
        # instead of keeping the stale number. See resolve_start_position.
        last_book, last_chapter, last_hadith = resolve_start_position(
            existing, start_book_id, start_chapter_id, start_hadith_id
        )
        save_channel_state(
            str(target.id),
            last_hadith,
            pick(start_name, "last_name_no", 1),
            last_book,
            last_chapter,
            clear_stopped=True,
            hadiths_per_day=hpd,
            names_per_day=npd,
            channel_name=target.name,
            guild_id=str(target.guild.id),
            guild_name=target.guild.name,
            guild_member_count=target.guild.member_count,
            name_match_enabled=name_match,
            ayah_enabled=quran_verse,
        )
        verb = "updated for" if existing else "set up for"
        reply = setup_reply(target.mention, verb, hpd, npd)
        if name_match is not None:
            reply += (
                f"\nThe daily name match game is now **{'on' if name_match else 'off'}** "
                f"in {target.mention}."
            )
        if quran_verse is not None:
            reply += (
                f"\nA daily verse of the Quran is now **{'on' if quran_verse else 'off'}** "
                f"in {target.mention}."
            )
        elif existing is None:
            # New channels get the verse without asking for it, so say so
            # while the admin is here, along with how to leave it out.
            reply += (
                "\nEach day's message also starts with a verse of the Quran. To leave "
                "it out, run `/bismillah setup quran_verse:False` in that channel."
            )
        await interaction.followup.send(reply, ephemeral=True)

    @app_commands.command(name="stop")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(
        channel="Channel to stop sending messages to (defaults to this channel)"
    )
    async def stop(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        target = channel or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.followup.send(
                "Please pick a text channel (or run this inside one).",
                ephemeral=True,
            )
            return
        stop_channel(str(target.id), STOPPED_BY_ADMIN)
        await interaction.followup.send(
            f"Daily messages will no longer be sent to {target.mention}. "
            "To start them again from where they left off, run `/bismillah setup` there.",
            ephemeral=True,
        )

    @app_commands.command(name="status")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def status(self, interaction: discord.Interaction):
        """Show which channels in this server have daily messages set up."""
        await interaction.response.defer(ephemeral=True)
        try:
            rows = get_all_channels()
        except Exception:
            self.bot.logger.error("Failed to fetch channel states", exc_info=True)
            await interaction.followup.send(
                "Couldn't fetch the channel status right now. Please try again later.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        limits = load_custom_limits()
        lines: List[str] = []
        for row in rows:
            # Resolve against this guild so only channels in *this* server show.
            # A channel from another server (or a deleted one) won't resolve here.
            channel = guild.get_channel(int(row["channel_id"])) if guild else None
            if channel is None:
                continue
            if row.get("stopped_at"):
                lines.append(f"{channel.mention} · ⏹️ {stopped_text(row)}")
                continue
            lines.append(
                f"{channel.mention} · 🟢 sending · "
                f"{daily_count(row.get('hadiths_per_day'), channel_max(row['channel_id'], limits))} hadith/"
                f"{daily_count(row.get('names_per_day'), channel_max(row['channel_id'], limits))} name(s) per day "
                f"(next: book {row['last_book_id']}, chapter {row['last_chapter_id']}, "
                f"hadith {row['last_hadith_no']}, name #{row['last_name_no']})"
                + (" · plus a verse of the Quran" if ayah_on(row) else "")
            )

        if not lines:
            await interaction.followup.send(
                "No channels are set up in this server yet. "
                "Use `/bismillah setup` to start daily messages in a channel.",
                ephemeral=True,
            )
            return

        await self._send_reference(
            interaction,
            f"**Daily message channels here** ({len(lines)} set up). "
            "Messages go out daily at 6:00 PM Toronto time:",
            lines,
        )

    @app_commands.command(name="diagnose")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(
        send_test="Actually post a test message to each channel (default: check only)"
    )
    async def diagnose(
        self, interaction: discord.Interaction, send_test: Optional[bool] = False
    ):
        """Check why the daily message may not be arriving in a channel.

        Walks the same path send_daily_message does -- cache lookup, then
        permissions -- and reports where it breaks, instead of failing silently
        at 6pm. With send_test, it also attempts a real post so Discord's own
        error (not our guess at it) is surfaced."""
        await interaction.response.defer(ephemeral=True)
        try:
            rows = get_all_channels()
        except Exception:
            self.bot.logger.error("Failed to fetch channel states", exc_info=True)
            await interaction.followup.send(
                "Couldn't fetch the channel status right now. Please try again later.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if guild is None:
            await interaction.followup.send("Run this inside a server.", ephemeral=True)
            return

        # Only rows belonging to this guild. Match on the stored guild_id rather
        # than resolving the channel, because an unresolvable channel is exactly
        # the failure we're here to report -- filtering on it would hide it.
        mine = [r for r in rows if str(r.get("guild_id")) == str(guild.id)]
        if not mine:
            await interaction.followup.send(
                "No channels are set up in this server yet. "
                "Use `/bismillah setup` to start daily messages in a channel.",
                ephemeral=True,
            )
            return

        lines: List[str] = []
        for row in mine:
            channel_id = row["channel_id"]
            label = row.get("channel_name") or channel_id
            if row.get("stopped_at"):
                lines.append(f"⏹️ **{label}**: {stopped_text(row)}")
                continue

            channel = self.bot.get_channel(int(channel_id))
            if channel is None:
                lines.append(
                    f"❌ **{label}** (`{channel_id}`) — the bot cannot see this channel. "
                    "Either it was added to your account instead of the server "
                    "(re-invite it with the **bot** scope), it was removed, or it "
                    "lacks **View Channel** here."
                )
                continue

            perms = channel.permissions_for(guild.me)
            missing = [
                name
                for name, ok in (
                    ("View Channel", perms.view_channel),
                    ("Send Messages", perms.send_messages),
                )
                if not ok
            ]
            if missing:
                lines.append(
                    f"❌ {channel.mention} — missing {', '.join(f'**{m}**' for m in missing)}."
                )
                continue

            if not send_test:
                lines.append(f"✅ {channel.mention} — looks deliverable.")
                continue

            try:
                await channel.send(
                    "🧪 HadithBot test message — daily delivery to this channel is working."
                )
                lines.append(f"✅ {channel.mention} — test message sent.")
            except discord.HTTPException as e:
                # The real reason, straight from Discord, rather than our inference.
                lines.append(f"❌ {channel.mention} — send failed: `{e.text or e}`")
                self.bot.logger.error(
                    f"Diagnose test send failed for channel {channel_id}: {e}",
                    exc_info=True,
                )

        await self._send_reference(
            interaction,
            f"**Delivery check** ({len(mine)} configured):",
            lines,
        )

    @app_commands.command(name="send-now")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(
        channel="Channel to send to (defaults to this channel)",
    )
    async def send_now(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
    ):
        """Send this channel's daily message right now, without waiting for 6pm.

        Runs the real broadcast for one channel, so what you see is what 6pm
        would have produced. That means it genuinely advances the reading
        position -- it is a real delivery, not a preview."""
        await interaction.response.defer(ephemeral=True)
        target = channel or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.followup.send(
                "Please pick a text channel (or run this inside one).",
                ephemeral=True,
            )
            return

        if get_channel_state(str(target.id)) is None:
            await interaction.followup.send(
                f"{target.mention} isn't set up yet — run `/bismillah setup` there first.",
                ephemeral=True,
            )
            return

        delivered = await self.bot.run_daily_broadcast(only_channel_id=str(target.id))
        if delivered:
            await interaction.followup.send(
                f"Sent today's message to {target.mention}. Its place has moved "
                "forward, so tomorrow continues from after this one.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"Nothing was sent to {target.mention}. It may not be set up, or it "
                "was stopped. Run `/bismillah diagnose` to see what's blocking it.",
                ephemeral=True,
            )

    async def _send_reference(
        self, interaction: discord.Interaction, header: str, lines: List[str]
    ):
        """Send a header + list as one or more ephemeral followups, each within
        Discord's 2000-character message limit."""
        chunk = header
        for line in lines:
            if len(chunk) + len(line) + 1 > 1900:
                await interaction.followup.send(chunk, ephemeral=True)
                chunk = ""
            chunk = f"{chunk}\n{line}" if chunk else line
        if chunk:
            await interaction.followup.send(chunk, ephemeral=True)

    @app_commands.command(name="books")
    async def books(self, interaction: discord.Interaction):
        """List all books and their ids (for use with /bismillah setup)."""
        await interaction.response.defer(ephemeral=True)
        lines = [f"`{b['id']}` — {b['english_title']}" for b in get_books()]
        lines.append(BOOKS_PAGE_HINT)
        await self._send_reference(
            interaction,
            "**Books** — use the number as `start_book_id` in `/bismillah setup`:",
            lines,
        )

    @app_commands.command(name="chapters")
    @app_commands.describe(book="Book id (see /bismillah books)")
    async def chapters(self, interaction: discord.Interaction, book: int):
        """List the chapters and their ids in a book."""
        await interaction.response.defer(ephemeral=True)
        chapters = get_chapters(book)
        if not chapters:
            await interaction.followup.send(
                f"No chapters found for book `{book}`. See `/bismillah books` for valid ids.",
                ephemeral=True,
            )
            return
        lines = [f"`{c['id']}` — {c['english']}" for c in chapters]
        lines.append(BOOKS_PAGE_HINT)
        await self._send_reference(
            interaction,
            f"**Chapters in book {book}** — use the number as `start_chapter_id` in `/bismillah setup`:",
            lines,
        )

    @app_commands.command(name="flags")
    @app_commands.describe(
        resolve="Hadith id to mark as dealt with (leave blank to just list open flags)"
    )
    async def flags(
        self, interaction: discord.Interaction, resolve: Optional[int] = None
    ):
        """Review hadiths readers have flagged. Bot owner only."""
        await interaction.response.defer(ephemeral=True)
        # Flags come in from every server the bot is in, so this is deliberately
        # not a per-guild admin command -- it would leak other servers' reports.
        if not await self.bot.is_owner(interaction.user):
            await interaction.followup.send(
                "Only the bot owner can review flags.", ephemeral=True
            )
            return

        if resolve is not None:
            closed = resolve_hadith_flags(resolve)
            await interaction.followup.send(
                f"Closed {closed} open flag(s) on hadith `{resolve}`."
                if closed
                else f"No open flags on hadith `{resolve}`.",
                ephemeral=True,
            )
            return

        open_flags = get_open_flags()
        if not open_flags:
            await interaction.followup.send("No open flags. 🎉", ephemeral=True)
            return

        # Group by hadith so a hadith several people flagged reads as one entry.
        grouped: dict[int, list[dict]] = {}
        for flag in open_flags:
            grouped.setdefault(flag["hadith_id"], []).append(flag)

        lines = []
        for hadith_id, entries in grouped.items():
            hadith = entries[0].get("hadiths") or {}
            snippet = " ".join((hadith.get("english_text") or "").split())[:160]
            lines.append(
                f"\n**`{hadith_id}`** — {len(entries)} flag(s) "
                f"· book {hadith.get('book_id')} ch {hadith.get('chapter_id')} "
                f"#{hadith.get('id_in_book')}\n{snippet}…"
            )
            for entry in entries:
                # <@id> renders as the member's name, so reports are attributable
                # without storing usernames that go stale when people rename.
                who = f"<@{entry['user_id']}>"
                where = entry.get("guild_name") or "unknown server"
                note = f" — “{entry['reason']}”" if entry.get("reason") else ""
                lines.append(f"↳ {who} in {where}{note}")
        lines.append(
            "\n-# `/bismillah flags resolve:<hadith id>` closes one; "
            "`/bismillah flag-reply` messages whoever reported it."
        )
        await self._send_reference(
            interaction, f"**{len(grouped)} flagged hadith(s)**", lines
        )

    @app_commands.command(name="flag-reply")
    @app_commands.describe(
        hadith="Hadith id to reply about (the id shown by /bismillah flags)",
        message="What to send the people who flagged it",
    )
    async def flag_reply(
        self, interaction: discord.Interaction, hadith: int, message: str
    ):
        """DM everyone who flagged a hadith. Bot owner only."""
        await interaction.response.defer(ephemeral=True)
        if not await self.bot.is_owner(interaction.user):
            await interaction.followup.send(
                "Only the bot owner can reply to reporters.", ephemeral=True
            )
            return

        flags = get_flags_for_hadith(hadith)
        if not flags:
            await interaction.followup.send(
                f"Nobody has flagged hadith `{hadith}`.", ephemeral=True
            )
            return

        body = compose_flag_reply(flags[0].get("hadiths") or {}, message)
        delivered, blocked = [], []
        # One DM per person even if they flagged from several servers.
        for user_id in dict.fromkeys(f["user_id"] for f in flags):
            try:
                user = self.bot.get_user(int(user_id)) or await self.bot.fetch_user(
                    int(user_id)
                )
                await user.send(body)
                delivered.append(user_id)
            except (discord.Forbidden, discord.HTTPException, ValueError):
                # Closed DMs are the common case here, not an error worth raising.
                blocked.append(user_id)

        report = f"Sent to {len(delivered)} of {len(delivered) + len(blocked)} reporter(s)."
        if blocked:
            report += (
                "\nCouldn't DM "
                + ", ".join(f"<@{u}>" for u in blocked)
                + " — they likely have DMs from server members turned off."
            )
        await interaction.followup.send(report, ephemeral=True)


def main():
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )

    bot = HadithBot()
    bot.tree.add_command(HadithCommands(bot))
    discord_token = os.getenv("DISCORD_TOKEN")

    if discord_token is None:
        raise Exception("DISCORD_TOKEN is not set")

    try:
        bot.run(discord_token or "", log_handler=None)
    except Exception as e:
        logging.error(f"Failed to start bot: {e}")
        raise


if __name__ == "__main__":
    main()
