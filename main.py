import discord
import asyncio
from discord.ext import commands, tasks
from discord import app_commands
import os

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='.', intents=intents)

with open("BOT_TOKEN", "r") as f:
	BOT_TOKEN = f.read()
	
@bot.event
async def on_ready():
	print(f'Logged in as {bot.user} (ID: {bot.user.id})')
	print('------')
	auto_leave_voice_channel.start()
	
@tasks.loop(seconds=30)
async def auto_leave_voice_channel():
	song_guesser = bot.get_cog("SongGuesser")
	await song_guesser.check_auto_stop()

async def load():
	for filename in os.listdir('./cogs'):
		if filename.endswith('.py'):
			await bot.load_extension(f'cogs.{filename[:-3]}')

async def main():
	await load()
	await bot.start(BOT_TOKEN)

asyncio.run(main())