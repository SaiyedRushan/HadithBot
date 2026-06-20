from datetime import time
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
    get_books,
    get_chapters,
    get_channels,
    get_hadith_in_same_chapter_and_book,
    get_random_hadith,
    remove_channel_state,
    save_channel_state,
)
from utils import Name, getHadithFormattedMessage, getNameFormattedMessage


class HadithBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

        self.names: List[Name] = []
        self.logger = logging.getLogger("HadithBot")

        # Setup error handling
        self.setup_error_handlers()

    async def setup_hook(self):
        """Initialize bot data and sync commands"""
        await self.load_data()
        await self.tree.sync()
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

    # @tasks.loop(seconds=10)
    @tasks.loop(time=time(hour=18, tzinfo=ZoneInfo("America/Toronto")))
    async def send_daily_message(self):
        """Loops through the active channels and sends daily messages"""
        try:
            channels = get_channels()
        except Exception as e:
            self.logger.error(f"Failed to fetch active channels: {e}")
            return

        for channel_row in channels.data:
            channel_id = channel_row["channel_id"]
            # Isolate each channel so one failure (e.g. missing permissions)
            # doesn't stop the broadcast to the remaining channels.
            try:
                last_hadith_no = channel_row["last_hadith_no"]
                last_name_no = channel_row["last_name_no"]
                last_book_no = channel_row["last_book_id"]
                last_chapter_no = channel_row["last_chapter_id"]

                channel = self.get_channel(int(channel_id))
                if not channel:
                    self.logger.error(f"Channel {channel_id} not found")
                    continue

                last_hadith_no, last_book_no, last_chapter_no = (
                    find_valid_hadith_position(
                        last_hadith_no, last_book_no, last_chapter_no
                    )
                )

                # send greeting
                await channel.send(
                    "> # Assalamu Alaikum Warahmatullahi Wabarakatuh, here is today's hadith and one of Allah's beautiful name\n"
                )
                # get name and send message
                names = self.get_names(last_name_no, 3)
                current_name_index = self.get_next_index(
                    last_name_no, len(self.names), 3
                )
                await self.send_formatted_name(channel, names)

                # get hadith for the given hadith number, book number, chapter number and send message
                hadith = get_hadith_in_same_chapter_and_book(
                    last_hadith_no, last_book_no, last_chapter_no, 3
                )

                if hadith:
                    for h in hadith:
                        await self.send_formatted_hadith(channel, h)
                        last_hadith_no = h["id_in_book"]

                    # Calculate next hadith position for tomorrow
                    next_hadith_no = last_hadith_no + 1

                    save_channel_state(
                        channel_id,
                        next_hadith_no,
                        current_name_index,
                        last_book_no,
                        last_chapter_no,
                    )

                    self.logger.info(
                        f"Successfully sent hadith from book {last_book_no}, chapter {last_chapter_no}, hadith {last_hadith_no}"
                    )
                else:
                    self.logger.error(
                        f"No hadith data returned for book {last_book_no}, chapter {last_chapter_no}, hadith {last_hadith_no}"
                    )
            except Exception as e:
                self.logger.error(
                    f"Failed to send daily message to channel {channel_id}: {e}",
                    exc_info=True,
                )

    @send_daily_message.before_loop
    async def before_daily_message(self):
        """Wait for the bot to be ready before starting the task"""
        await self.wait_until_ready()
        self.logger.info("\nDaily message task is ready to start\n")

    def get_names(self, number: int, count: int = 1) -> Optional[List[Name]]:
        """Get name by number with validation"""
        if 1 <= number <= len(self.names):
            return self.names[number - 1 : number + count - 1]
        return None

    @staticmethod
    def get_next_index(current: int, max_value: int, increment: int = 1) -> int:
        """Get next index with wraparound"""
        return (current + increment) if (current + increment < max_value) else 1

    async def send_formatted_hadith(self, channel: discord.TextChannel, hadith: dict):
        """Send formatted hadith message"""
        if not hadith:
            return
        formatted_messages = getHadithFormattedMessage(hadith)
        for message in formatted_messages:
            await channel.send(message)

    async def send_formatted_name(
        self, channel: discord.TextChannel, names: List[Name]
    ):
        """Send formatted name messages for multiple names"""
        if not names:
            return
        for name in names:
            formatted_message = getNameFormattedMessage(name)
            await channel.send(formatted_message)


# Command group for better organization
@app_commands.guild_only()
class HadithCommands(app_commands.Group):
    def __init__(self, bot: HadithBot):
        super().__init__(name="bismillah")
        self.bot = bot

    @app_commands.command(name="random")
    async def random(self, interaction: discord.Interaction):
        await interaction.response.defer()
        hadith = get_random_hadith()
        await self.bot.send_formatted_hadith(interaction.channel, hadith)
        await interaction.followup.send("Here is a random hadith", ephemeral=True)

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
        hadith = get_hadith_in_same_chapter_and_book(hadith_no, book_no, chapter_no)
        if not hadith:
            await interaction.response.send_message(
                "No hadith found for that book, chapter, and hadith combination.",
                ephemeral=True,
            )
            return
        hadith = hadith[0]
        await interaction.response.defer()
        await self.bot.send_formatted_hadith(interaction.channel, hadith)
        await interaction.followup.send(
            "Here is the hadith you requested", ephemeral=True
        )

    async def _send_names(
        self,
        interaction: discord.Interaction,
        names: Optional[List[Name]],
        success_message: str,
    ):
        """Validate the requested names, then send them to the channel."""
        if not names:
            await interaction.response.send_message(
                f"Invalid name number. Please choose between 1 and {len(self.bot.names)}",
                ephemeral=True,
            )
            return
        await interaction.response.defer()
        await self.bot.send_formatted_name(interaction.channel, names)
        await interaction.followup.send(success_message, ephemeral=True)

    @app_commands.command(name="random_name")
    async def random_name(self, interaction: discord.Interaction):
        names = self.bot.get_names(random.randint(1, len(self.bot.names)), 1)
        await self._send_names(
            interaction, names, "Here is one of Allah's beautiful names"
        )

    @app_commands.command(name="specific_names")
    @app_commands.describe(number="The starting number of the names")
    async def specific_names(self, interaction: discord.Interaction, number: int):
        names = self.bot.get_names(number, 3)
        await self._send_names(
            interaction, names, "Here are three of Allah's beautiful names"
        )

    @app_commands.command(name="specific_name")
    @app_commands.describe(number="The number of the name")
    async def specific_name(self, interaction: discord.Interaction, number: int):
        names = self.bot.get_names(number, 1)
        await self._send_names(interaction, names, "Here is the name you requested")

    @app_commands.command(name="setup")
    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.describe(
        channel="Channel to send daily messages to (defaults to this channel)",
        start_book_id="Book id to start from — see /bismillah books (optional; defaults to the beginning)",
        start_chapter_id="Chapter id to start from — see /bismillah chapters (optional; defaults to the beginning)",
        start_hadith_id="Hadith id to start from (optional; defaults to the beginning)",
        start_name="Name number to start from (optional; defaults to 1)",
    )
    async def setup(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        start_book_id: int = 1,
        start_chapter_id: int = 1,
        start_hadith_id: int = 1,
        start_name: int = 1,
    ):
        await interaction.response.defer(ephemeral=True)
        target = channel or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.followup.send(
                "Please pick a text channel (or run this inside one).",
                ephemeral=True,
            )
            return
        save_channel_state(
            str(target.id),
            start_hadith_id,
            start_name,
            start_book_id,
            start_chapter_id,
            active=True,
        )
        await interaction.followup.send(
            f"Daily hadith and names will now be sent to {target.mention}.",
            ephemeral=True,
        )

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
        remove_channel_state(str(target.id))
        await interaction.followup.send(
            f"Daily messages will no longer be sent to {target.mention}.",
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
        await self._send_reference(
            interaction,
            f"**Chapters in book {book}** — use the number as `start_chapter_id` in `/bismillah setup`:",
            lines,
        )


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
