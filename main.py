import discord
import asyncio
from discord.ext import commands, tasks
from discord import app_commands
import os

# 需依賴 ffmpeg 程式 (目前僅支援 windows)
from shutil import which
import urllib.request
import zipfile
if which("ffmpeg") == None or which("ffprobe") == None:
	last_percent = "0%"
	print(f"ffmpeg not found, downloading... {last_percent}", end="", flush=True)
	def update_progress(block_num, block_size, total_size):
		global last_percent
		percent = f"{int(block_num * block_size * 100 / total_size)}%"
		print("\b" * len(last_percent), end="")
		print(percent, end="")
		last_percent = percent
		
	try:
		urllib.request.urlretrieve("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip", "ffmpeg.zip", update_progress)
	except Exception as e:
		print(f"\nError while downloading ffmpeg! ({e})")
		exit(1)
		
	print("\nffmpeg downloaded, extracting files...")
	with zipfile.ZipFile("ffmpeg.zip", "r") as zip:
		for file in zip.namelist():
			if file.endswith("ffmpeg.exe") or file.endswith("ffprobe.exe"):
				zip.extract(file)
				os.rename(file, os.path.basename(file))
				
	os.remove("ffmpeg.zip")
	print("ffmpeg install finished, starting bot...")
	
from cogs import song_guesser



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
	await bot.load_extension('cogs.song_guesser')

async def main():
	await load()
	await bot.start(BOT_TOKEN)

try:
	asyncio.run(main())
except KeyboardInterrupt:
	print("Bot disconnected!")