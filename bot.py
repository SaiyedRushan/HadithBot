from datetime import datetime, time
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
import random
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
import aiofiles
import json
from zoneinfo import ZoneInfo
from db import save_channel_state, get_channels, remove_channel_state

from utils import getHadithFormattedMessage, getNameFormattedMessage

# Data models
@dataclass
class HadithChapter:
    chapter: str
    hadiths: List[str]

@dataclass
class Name:
    number: int
    name: str
    transliteration: str
    found: str
    en: Dict[str, str]
    fr: Dict[str, str]

class HadithBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix='!', intents=intents)
        
        # Initialize storage
        self.messages: List[HadithChapter] = []
        self.names: List[Name] = []
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('HadithBot')
        
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
            # Read and parse hadiths.json
            async with aiofiles.open('data/hadiths.json', mode='r') as file:
                messages_data = json.loads(await file.read())
                self.messages = [HadithChapter(**msg) for msg in messages_data]
 
            # Read and parse 99names.json
            async with aiofiles.open('data/99names.json', mode='r') as file:
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
        async def on_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            if isinstance(error, app_commands.CommandOnCooldown):
                await interaction.response.send_message(
                    f"Please wait {error.retry_after:.2f} seconds before using this command again.",
                    ephemeral=True
                )
            else:
                self.logger.error(f"Command error: {error}", exc_info=True)
                await interaction.response.send_message(
                    "An error occurred while processing your command. Please try again later.",
                    ephemeral=True
                )

    @tasks.loop(time=time(hour=18, tzinfo=ZoneInfo("America/Toronto")))
    async def send_daily_message(self):
        """Loops through the active channels and sends daily messages"""
        try:
            channels = get_channels()

            for channel in channels.data:
                channel_id = channel['channel_id']
                last_hadith_no = channel['last_hadith_no']
                last_name_no = channel['last_name_no']

                channel = self.get_channel(int(channel_id))
                if not channel:
                    self.logger.error(f"Channel {channel_id} not found")
                    continue

                hadith = self.get_hadith(last_hadith_no)
                current_chapter = self.get_next_index(last_hadith_no, len(self.messages))
                name = self.get_name(last_name_no)
                current_name_index = self.get_next_index(last_name_no, len(self.names))

                await channel.send("> # Assalamu Alaikum Warahmatullahi Wabarakatuh, here is today's hadith and one of Allah's beautiful name\n")
                await self.send_formatted_hadith(channel, hadith)
                await self.send_formatted_name(channel, name)

                save_channel_state(channel_id, current_chapter, current_name_index)

        except Exception as e:
            self.logger.error(f"Failed to send daily message: {e}")
        
    @send_daily_message.before_loop
    async def before_daily_message(self):
        """Wait for the bot to be ready before starting the task"""
        await self.wait_until_ready()
        self.logger.info("Daily message task is ready to start")

    def get_hadith(self, chapter: int) -> Optional[HadithChapter]:
        """Get hadith by chapter number with validation"""
        if 1 <= chapter <= len(self.messages):
            return self.messages[chapter - 1]
        return None

    def get_name(self, number: int) -> Optional[Name]:
        """Get name by number with validation"""
        if 1 <= number <= len(self.names):
            return self.names[number - 1]
        return None

    @staticmethod
    def get_next_index(current: int, max_value: int) -> int:
        """Get next index with wraparound"""
        return (current + 1) if (current < max_value) else 1

    async def send_formatted_hadith(self, channel: discord.TextChannel, hadith: HadithChapter):
        """Send formatted hadith message"""
        if not hadith:
            return
        formatted_messages = getHadithFormattedMessage(hadith)
        for message in formatted_messages:
            await channel.send(message)

    async def send_formatted_name(self, channel: discord.TextChannel, name: Name):
        """Send formatted name message"""
        if not name:
            return
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
        hadith = self.bot.get_hadith(random.randint(1, len(self.bot.messages)))
        await interaction.response.defer()
        await self.bot.send_formatted_hadith(interaction.channel, hadith)
        await interaction.followup.send("Here is a random hadith", ephemeral=True)

    @app_commands.command(name="specific")
    @app_commands.describe(chapter="The chapter number of the hadith")
    async def specific(self, interaction: discord.Interaction, chapter: int):
        hadith = self.bot.get_hadith(chapter)
        if not hadith:
            await interaction.response.send_message(
                f"Invalid chapter number. Please choose between 1 and {len(self.bot.messages)}",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        await self.bot.send_formatted_hadith(interaction.channel, hadith)
        await interaction.followup.send("Here is the hadith you requested", ephemeral=True)



    @app_commands.command(name="random_name")
    async def random_name(self, interaction: discord.Interaction):
        name = self.bot.get_name(random.randint(1, len(self.bot.names)))
        await interaction.response.defer()
        await self.bot.send_formatted_name(interaction.channel, name)
        await interaction.followup.send("Here is one of Allah's beautiful names", ephemeral=True)


    @app_commands.command(name="specific_name")
    @app_commands.describe(number="The number of the name")
    async def specific_name(self, interaction: discord.Interaction, number: int):
        name = self.bot.get_name(number)
        if not name:
            await interaction.response.send_message(
                f"Invalid name number. Please choose between 1 and {len(self.bot.names)}",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        await self.bot.send_formatted_name(interaction.channel, name)
        await interaction.followup.send("Here is the name you requested", ephemeral=True)

    @app_commands.command(name="setup")
    @app_commands.describe(channel_id="The ID of the channel where you want to send messages")
    @app_commands.describe(start_chapter="The chapter number of the hadith you want to start with")
    @app_commands.describe(start_name="The number of the name you want to start with")
    async def setup(self, interaction: discord.Interaction, channel_id: str, start_chapter: int, start_name: int):
        await interaction.response.defer()
        save_channel_state(channel_id, start_chapter, start_name)
        await interaction.followup.send(f"Messages will now be sent to the channel with ID {channel_id}.")
        

    @app_commands.command(name="stop")
    @app_commands.describe(channel_id="The ID of the channel where you want to stop sending messages")
    async def stop(self, interaction: discord.Interaction, channel_id: str):
        await interaction.response.defer()
        remove_channel_state(channel_id)
        await interaction.followup.send("Messages will no longer be sent to this channel.")


    @app_commands.command(name="list")
    async def list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        channels = get_channels()
        await interaction.followup.send(f"Channels: {channels}")
        for channel in channels.data:
            c = self.bot.get_channel(int(channel['channel_id']))
            await interaction.followup.send(f"Channel ID: {c.name}, Last Hadith No: {channel['last_hadith_no']}, Last Name No: {channel['last_name_no']}")
def main():
    load_dotenv()
    bot = HadithBot()
    bot.tree.add_command(HadithCommands(bot))
    
    try:
        bot.run(os.getenv('DISCORD_TOKEN'), log_handler=None)
    except Exception as e:
        logging.error(f"Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    main()