# This example requires the 'message_content' privileged intent to function.

import asyncio
import json

import discord
from youtube_dl import youtube_dl
from pydub import AudioSegment

from discord.ext import commands
from discord import app_commands

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
		self.channel = None
		self.question_set = None
	
class SongGuesser(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.games = dict()	 # <Guild, GameData>

	@app_commands.command()
	async def init(self, interaction):
		"""在當前語音頻道舉行猜歌遊戲"""
		
		if not interaction.user.voice:
			await interaction.response.send_message("你必須在一個語音頻道中才能執行這個指令", ephemeral=True)
			return
			
		if interaction.guild.id not in self.games:
			self.games[interaction.guild.id] = GameData()
		game = self.games[interaction.guild.id]
			
		if game.step != GameStep.IDLE:
			await interaction.response.send_message(f"當前伺服器已在 <#{game.channel.id}> 進行遊戲，請先使用 /stop 指令中斷再試", ephemeral=True)
			return
		
		game.channel = interaction.user.voice.channel
		voice_client = interaction.guild.voice_client
		if voice_client is None:
			await interaction.user.voice.channel.connect()
		else:
			if voice_client.is_playing():
				voice_client.stop()
			await voice_client.move_to(interaction.user.voice.channel)
		
		await interaction.response.send_message(f"猜歌遊戲在 <#{game.channel.id}> 舉行，請先上傳題庫檔案！")

	@app_commands.command()
	async def start(self, interaction):
		"""開始一場猜歌遊戲"""
			
		if interaction.guild.id not in self.games:
			await interaction.response.send_message("請先輸入 init 指令舉行遊戲", ephemeral=True)
			return
			
		game = self.games[interaction.guild.id]
		if not interaction.user.voice or interaction.user.voice.channel != game.channel:
			await interaction.response.send_message(f"請先加入舉行遊戲的 <#{game.channel.id}> 頻道", ephemeral=True)
			return
			
		if game.step != GameStep.IDLE:
			await interaction.response.send_message("遊戲正在進行中，請直接使用遊戲相關指令參與！", ephemeral=True)
			return
		
		game.step = GameStep.PLAYING

	# @app_commands.command()
	# async def yt(self, interaction, *, url: str):
		# """播放 youtube 音樂"""
		
		# await interaction.response.defer(ephemeral=True)
		# voice_check = await self.ensure_voice(interaction)
		# if not voice_check:
			# return
			
		# voice_client = interaction.guild.voice_client
		# player = await YTDLSource.from_url(url, loop=self.bot.loop)
		# voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)

		# await interaction.response.send_message(f'Now playing: {player.title}', ephemeral=True)

	async def check_auto_stop(self):
		for guild in self.bot.guilds:
			for vc in guild.voice_channels:
				if len(vc.members) == 1 and self.bot.user in vc.members:
					await vc.guild.voice_client.disconnect()
					if guild.id in self.games:
						del self.games[guild.id]
		
	@app_commands.command()
	async def stop(self, interaction):
		"""把機器人驅逐出去"""
		
		if interaction.guild.id not in self.games:
			await interaction.response.send_message("當前伺服器沒有舉行中的猜歌遊戲", ephemeral=True)
			return
		
		voice_client = interaction.guild.voice_client
		if voice_client is not None:
			await voice_client.disconnect()
			
		game = self.games[interaction.guild.id]
		await interaction.response.send_message(f"已中斷在 <#{game.channel.id}> 舉行的猜歌遊戲")
		del self.games[interaction.guild.id]
	
	@app_commands.command()
	async def upload(self, interaction, attachment: discord.Attachment):
		"""上傳一份題庫檔案"""
		
		if interaction.guild.id not in self.games:
			await interaction.response.send_message("你必須先開始一場遊戲")
			return
		
		game = self.games[interaction.guild.id]
		if game.step != GameStep.IDLE:
			await interaction.response.send_message("遊戲正在進行中，只有等待階段可以上傳題庫")
			return
			
		if attachment.filename.endswith('.json'):
			data = await attachment.read()
			game.question_set = json.loads(data.decode("utf8"))
			await interaction.response.send_message(f'已成功上傳題庫 {attachment.filename}')
		
	# =========================================================================================
		
	@commands.command()
	async def sync(self, ctx) -> None:
		fmt = await ctx.bot.tree.sync()
		await ctx.send(f"Synced {len(fmt)} commands")



async def setup(bot):
	await bot.add_cog(SongGuesser(bot))