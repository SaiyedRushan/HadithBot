from datetime import datetime, timedelta
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from dotenv import load_dotenv
import os
import random
from server import keep_alive
from utils import getNameFormattedMessage, load_messages, getHadithFormattedMessage, loadNames
load_dotenv()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# an array of hadiths
messages = load_messages()
names = loadNames() 

# Send daily message
async def send_daily_message(channel_id, startChapter, startName):
    channel = bot.get_channel(channel_id)
    current_chapter = startChapter if startChapter > 0 and startChapter <= len(messages) else 1
    current_name_index = startName if startName > 0 and startName <= len(names) else 1

    while True:
        # Wait until 6:00 AM
        now = datetime.now()
        target_time = now.replace(hour=6, minute=0, second=0, microsecond=0)
        if now >= target_time:
            target_time += timedelta(days=1)
        wait_seconds = (target_time - now).total_seconds()
        print(f'Waiting for {wait_seconds} seconds')
        await asyncio.sleep(wait_seconds)

        # send hadith
        formatted_messages = getHadithFormattedMessage(messages, current_chapter)
        for message in formatted_messages:
            await channel.send(message)
        current_chapter = (current_chapter + 1) if (current_chapter < len(messages) and current_chapter > 0) else 1
    
        # send name
        formatted_name_message = f"> **Today's Name**\n"
        formatted_name_message += getNameFormattedMessage(names, current_name_index)
        await channel.send(formatted_name_message)
        current_name_index = (current_name_index + 1) if (current_name_index < len(names) and current_name_index > 0) else 1

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
@app_commands.describe(start_chapter='The chapter number of the hadith you want to start with')
@app_commands.describe(start_name='The number of the name you want to start with')
async def setup(interaction: discord.Interaction, channel_id:str, start_chapter:int, start_name:int):
    await interaction.response.send_message(f'Messages will now be sent to the channel with ID {channel_id}.')
    bot.loop.create_task(send_daily_message(int(channel_id), start_chapter, start_name))


@bot.tree.command(name='randomhadith')
async def randomHadith(interaction: discord.Interaction):
    formatted_messages = getHadithFormattedMessage(messages, random.randint(1, len(messages)))
    await interaction.response.send_message(formatted_messages[0])
    for message in formatted_messages[1:]:
        await interaction.followup.send(message)

@bot.tree.command(name='specifichadith')
@app_commands.describe(chapter='The chapter number of the hadith you want to hear')
async def specificHadith(interaction: discord.Interaction, chapter: int):
    formatted_messages = getHadithFormattedMessage(messages, chapter)
    await interaction.response.send_message(formatted_messages[0])
    for message in formatted_messages[1:]:
        await interaction.followup.send(message)

@bot.tree.command(name='randomname')
async def randomName(interaction: discord.Interaction):
    await interaction.response.send_message(getNameFormattedMessage(names, random.randint(1, len(names))))       
    
@bot.tree.command(name='specificname')
@app_commands.describe(number='The number of the name you want to hear')
async def specificName(interaction: discord.Interaction, number: int):
    await interaction.response.send_message(getNameFormattedMessage(names, number))

# keep_alive()
bot.run(os.getenv('TOKEN'))