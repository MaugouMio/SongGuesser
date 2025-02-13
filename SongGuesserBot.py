# This example requires the 'message_content' privileged intent to function.

import asyncio
import json

import discord
from youtube_dl import youtube_dl
from pydub import AudioSegment

from discord.ext import commands, tasks

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
	'format': 'bestaudio/best',
	'outtmpl': 'temp/main',
	'restrictfilenames': True,
	'noplaylist': True,
	'nocheckcertificate': True,
	'ignoreerrors': False,
	'logtostderr': False,
	'quiet': True,
	'no_warnings': True,
	'default_search': 'auto',
	'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
	'options': '-vn',
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
	def __init__(self, source, *, data, volume=0.5):
		super().__init__(source, volume)

		self.data = data

		self.title = data.get('title')
		self.url = data.get('url')

	@classmethod
	async def from_url(cls, url, *, loop=None, stream=False):
		loop = loop or asyncio.get_event_loop()
		data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

		if 'entries' in data:
			# take first item from a playlist
			data = data['entries'][0]
			
		song = AudioSegment.from_file("temp/main", "m4a")

		filename = data['url'] if stream else ytdl.prepare_filename(data)
		return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)



class GameStep:
	IDLE = 0
	PLAYING = 1

class GameData:
	def __init__(self):
		self.step = GameStep.IDLE
	
class SongGuesser(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.games = dict()  # <Guild, GameData>

	@commands.command()
	async def start(self, ctx):
		"""Starts a new game"""
		game = self.games.get(ctx.guild)
		if game.step != GameStep.IDLE:
			await ctx.send("當前伺服器已經有遊戲正在進行中")
			return
		
		game.step = GameStep.PLAYING

	@commands.command()
	async def yt(self, ctx, *, url):
		"""Plays from a url (almost anything youtube_dl supports)"""

		async with ctx.typing():
			player = await YTDLSource.from_url(url, loop=self.bot.loop)
			ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

		await ctx.send(f'Now playing: {player.title}')

	@commands.command()
	async def volume(self, ctx, volume: int):
		"""Changes the player's volume"""

		if ctx.voice_client is None:
			return await ctx.send("Not connected to a voice channel.")

		ctx.voice_client.source.volume = volume / 100
		await ctx.send(f"Changed volume to {volume}%")

	@commands.command()
	async def stop(self, ctx):
		"""Stops and disconnects the bot from voice"""

		await ctx.voice_client.disconnect()

	@start.before_invoke
	@yt.before_invoke
	async def ensure_voice(self, ctx):
		if ctx.voice_client is None:
			if ctx.author.voice:
				await ctx.author.voice.channel.connect()
			else:
				await ctx.send("You are not connected to a voice channel.")
				raise commands.CommandError("Author not connected to a voice channel.")
		elif ctx.voice_client.is_playing():
			ctx.voice_client.stop()
		
	# =========================================================================================
	
	@commands.command()
	async def upload(self, ctx):
		if ctx.message.attachments:
			attachment = ctx.message.attachments[0]
			if attachment.filename.endswith('.json'):
				data = await attachment.read()
				question_set = json.loads(data.decode("utf8"))
				await ctx.send(f'已成功上傳題庫 {attachment.filename}')
				return
		await ctx.send('請在發送指令的訊息中附帶題庫的 JSON 檔案')


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
	command_prefix=commands.when_mentioned_or("!"),
	description='Song Guesser',
	intents=intents,
)

with open("BOT_TOKEN", "r") as f:
	BOT_TOKEN = f.read()


@bot.event
async def on_ready():
	print(f'Logged in as {bot.user} (ID: {bot.user.id})')
	print('------')
	auto_leave_voice_channel.start()
	
@tasks.loop(seconds=30)
async def auto_leave_voice_channel():
	for guild in bot.guilds:
		for vc in guild.voice_channels:
			if len(vc.members) == 1 and bot.user in vc.members:
				await vc.guild.voice_client.disconnect()


async def main():
	async with bot:
		await bot.add_cog(SongGuesser(bot))
		await bot.start(BOT_TOKEN)


asyncio.run(main())
