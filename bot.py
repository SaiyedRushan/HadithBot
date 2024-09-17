from datetime import datetime, timedelta
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from dotenv import load_dotenv
import os
import random
from server import keep_alive
from utils import load_messages, get_next_message, find_last_newline
load_dotenv()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# an array of hadiths
messages = load_messages()

# Send daily message
async def send_daily_message(channel_id):
    channel = bot.get_channel(channel_id)
    current_index = 0

    while True:
        # Wait until 6:00 AM
        now = datetime.now()
        target_time = now.replace(hour=6, minute=0, second=0, microsecond=0)
        if now >= target_time:
            target_time += timedelta(days=1)
        wait_seconds = (target_time - now).total_seconds()
        print(f'Waiting for {wait_seconds} seconds')
        await asyncio.sleep(wait_seconds)

        object, current_index = get_next_message(messages, current_index)

        formatted_message = f"> **{object['chapter']}**\n\n"
        for hadith in object['hadiths']:
            formatted_message += f"> {hadith}\n\n"
        
        while len(formatted_message) > 0:
            if len(formatted_message) <= 2000:
                await channel.send(formatted_message)
                formatted_message = ""
            else:
                # Find the last newline character within the first 2000 characters
                split_index = find_last_newline(formatted_message[:2000])
                if split_index == -1:
                    split_index = 2000
                # Send the first part of the message
                await channel.send(formatted_message[:split_index])
                # Update formatted_message to contain the remaining text
                formatted_message = formatted_message[split_index:].lstrip()

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    try:  
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} commands')
    except Exception as e:
        print('There was an error syncing the commands: ', e)


@bot.tree.command(name='setup')
@app_commands.describe(channel_id='The ID of the channel where you want to send messages')
async def setup(interaction: discord.Interaction, channel_id:str):
    await interaction.response.send_message(f'Messages will now be sent to the channel with ID {channel_id}.')
    bot.loop.create_task(send_daily_message(int(channel_id)))

@bot.tree.command(name='random')
async def randomMessage(interaction: discord.Interaction):
    object = messages[random.randint(0, len(messages) - 1)]
    
    chapter = f"> **{object['chapter']}**\n\n"
    hadiths = ""
    for hadith in object['hadiths']:
        hadiths += f"> {hadith}\n\n"

    await interaction.response.send_message(chapter)
    while len(hadiths) > 0:
      if len(hadiths) <= 2000:
          await interaction.followup.send(hadiths)
          hadiths = ""
      else:
          split_index = find_last_newline(hadiths[:2000])
          if split_index == -1:
              split_index = 2000
          await interaction.followup.send(hadiths[:split_index])
          hadiths = hadiths[split_index:].lstrip()

@bot.tree.command(name='specific')
@app_commands.describe(chapter='The chapter of the hadith you want to hear')
async def specificMessage(interaction: discord.Interaction, chapter: int):
    object = messages[chapter - 1]
    chapter_text = f"> **{object['chapter']}**\n\n"
    hadiths = ""
    for hadith in object['hadiths']:
        hadiths += f"> {hadith}\n\n"
        
    await interaction.response.send_message(chapter_text)
    while len(hadiths) > 0:
      if len(hadiths) <= 2000:
          await interaction.followup.send(hadiths)
          hadiths = ""
      else:
          split_index = find_last_newline(hadiths[:2000])
          if split_index == -1:
              split_index = 2000
          await interaction.followup.send(f"{hadiths[:split_index]}")
          hadiths = hadiths[split_index:].lstrip()

keep_alive()
bot.run(os.getenv('TOKEN'))