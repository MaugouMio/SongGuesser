# This example requires the 'message_content' privileged intent to function.

import asyncio
import json, os, random

import discord
from youtube_dl import youtube_dl
from pydub import AudioSegment

from discord.ext import commands
from discord import app_commands

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
	'format': 'bestaudio/best',
	# 'outtmpl': 'temp/main',  # set individually for each discord guild
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
ytdl_instances = dict()
class YTDLSource(discord.PCMVolumeTransformer):
	def __init__(self, source, *, data, volume=0.5):
		super().__init__(source, volume)

		self.data = data

		self.title = data.get('title')
		self.url = data.get('url')

	@classmethod
	async def load_from_url(cls, url, parts, guild_id, *, loop=None):
		directory = f"temp/{guild_id}"
		if guild_id not in ytdl_instances:
			if not os.path.exists(directory):
				os.mkdir(directory)
				
			options = ytdl_format_options.copy()
			options["outtmpl"] = f"{directory}/main"
			ytdl_instances[guild_id] = youtube_dl.YoutubeDL(options)
			
		ytdl = ytdl_instances[guild_id]
		loop = loop or asyncio.get_event_loop()
		data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=True))

		if 'entries' in data:
			# take first item from a playlist
			data = data['entries'][0]
			
		filename = f"{directory}/main"
		song = AudioSegment.from_file(filename, "m4a")
		for i in range(len(parts)):
			part = parts[i]
			song[part[0]:part[1]].export(f"{directory}/{i}", format="m4a")

	@classmethod
	async def get_part(cls, part, guild_id):
		filename = f"temp/{guild_id}/{part}"
		return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)



class GameStep:
	IDLE = 0		# 物件初始狀態
	WAITING = 1		# 遊戲剛開始還沒出題，或是已經結算完的狀態
	PLAYING = 2		# 出完題目正在等待玩家回答的狀態

class GameData:
	def __init__(self, guild_id, text_channel):
		self.guild_id = guild_id
		self.text_channel = text_channel
		
		self.step = GameStep.IDLE
		self.channel = None
		self.question_set = None
		self.current_question_idx = 0
		self.current_question_part = 0
	
	def reset_progress(self):
		self.current_question_idx = 0
		self.current_question_part = 0
		if self.question_set:
			random.shuffle(self.question_set["questions"])
	
	@staticmethod
	def is_valid_question_set(question_set):
		# TODO: 題目格式的檢查
		return True
	
class SongGuesser(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.games = dict()	 # <Guild, GameData>
	
	async def on_play_finished(self, e, game, message):
		if e:
			print(f"[{game.guild_id}] Play question {game.current_question_idx + 1} part {game.current_question_part + 1} error: {e}")
		asyncio.run(message.edit(f"第 {game.current_question_idx + 1} 題片段 {game.current_question_part + 1} 播放完畢，快用 `/猜` 指令搶答吧！"))
		
	async def play_part(self, game):
		source = await YTDLSource.get_part(game.current_question_part, game.guild_id)
		message = await game.text_channel.send(f"正在播放第 {game.current_question_idx + 1} 題片段 {game.current_question_part + 1}，使用 `/猜` 指令進行搶答")
		await asyncio.sleep(2)
		voice_client.play(source, after=lambda e, game=game, message=message: asyncio.get_running_loop().create_task(self.on_play_finished(e, game, message)))
	
	async def init_question(self, game):
		idx = game.current_question_idx
		await YTDLSource.load_from_url(game.question_set["questions"][idx]["url"], game.question_set["questions"][idx]["parts"], game.guild_id, loop=self.bot.loop)
		game.current_question_part = 0
		await self.play_part()
	
	# =========================================================================================

	@app_commands.command(name = "開始遊戲")
	async def start(self, interaction, attachment: discord.Attachment):
		"""上傳題庫，開始一場猜歌遊戲"""
		
		if interaction.guild.id not in self.games:
			text_channel = self.bot.get_channel(interaction.channel.id)
			self.games[interaction.guild.id] = GameData(interaction.guild.id, text_channel)
		game = self.games[interaction.guild.id]
		
		if game.step != GameStep.IDLE:
			await interaction.response.send_message(f"當前伺服器已在 <#{game.channel.id}> 進行遊戲，請先使用 `/結束遊戲` 指令中斷再試", ephemeral=True)
			return
		
		if not interaction.user.voice:
			await interaction.response.send_message(f"你必須在語音頻道內才能開啟一場遊戲", ephemeral=True)
			return
			
		try:
			data = await attachment.read()
			question_set = json.loads(data.decode("utf8"))
			if not GameData.is_valid_question_set(question_set):
				await interaction.response.send_message(f"題庫檔案 {attachment.filename} 的格式不符，無法開始遊戲", ephemeral=True)
				return
			game.question_set = question_set
		except:
			await interaction.response.send_message(f"上傳題庫檔案 {attachment.filename} 時發生錯誤，請檢查檔案內容是否正確", ephemeral=True)
			
		voice_client = interaction.guild.voice_client
		if voice_client is None:
			await interaction.user.voice.channel.connect()
		else:
			if voice_client.is_playing():
				voice_client.stop()
			await voice_client.move_to(interaction.user.voice.channel)
			
		game.channel = interaction.user.voice.channel
		game.step = GameStep.WAITING
		
		title = game.question_set["title"]
		await interaction.response.send_message(f"{interaction.user.name} 開始了 [{title}] 的猜歌遊戲\n加入 <#{game.channel.id}> 頻道一起遊玩吧！")
		
		#倒數後直接開始第一題
		message = await game.text_channel.send("遊戲將於 3 秒後開始...")
		for i in range(2, 0, -1):
			await asyncio.sleep(1)
			await message.edit(content=f"遊戲將於 {i} 秒後開始...")
		await asyncio.sleep(1)
		await message.edit(content=f"遊戲即將開始...")
		
		game.reset_progress()
		await self.init_question(game)
		
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
		
	@app_commands.command(name = "結束遊戲")
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
		
	# =========================================================================================
	
	async def game_command_pre_check(self, interaction):
		if interaction.guild.id not in self.games:
			await interaction.response.send_message("當前伺服器沒有舉行中的猜歌遊戲", ephemeral=True)
			return False
		
		game = self.games[interaction.guild.id]
		if not interaction.user.voice or interaction.user.voice.channel != game.channel:
			await interaction.response.send_message(f"你必須在遊戲進行中的 <#{game.channel.id}> 頻道才能使用遊戲指令", ephemeral=True)
			return False
		
		return True
	
	@app_commands.command(name = "下一題")
	async def question(self, interaction):
		"""[遊戲指令] 從題庫中隨機出題"""
		
		pre_check = await self.game_command_pre_check(interaction)
		if not pre_check:
			return
			
		await interaction.response.send_message("即將開始第 N 題")
	
	@app_commands.command(name = "更多片段")
	async def hint(self, interaction):
		"""[遊戲指令] 播放當前題目下一個音樂片段"""
		
		pre_check = await self.game_command_pre_check(interaction)
		if not pre_check:
			return
			
		await interaction.response.send_message("正在播放片段 X")
	
	@app_commands.command(name = "猜")
	async def guess(self, interaction, answer: str):
		"""[遊戲指令] 猜測當前題目的答案"""
		
		pre_check = await self.game_command_pre_check(interaction)
		if not pre_check:
			return
			
		# TODO: send_modal 讓他看相關的選項
		await interaction.response.send_message("X 猜了 Y")
	
	@app_commands.command(name = "結算")
	async def settle(self, interaction):
		"""[遊戲指令] 中止當前的遊戲並進行結算"""
		
		pre_check = await self.game_command_pre_check(interaction)
		if not pre_check:
			return
			
		game = self.games[interaction.guild.id]
		game.step = GameStep.WAITING
		await interaction.response.send_message("結算結果：")
	
	@app_commands.command(name = "重新開始")
	async def restart(self, interaction):
		"""[遊戲指令] 以目前的題庫重新進行一輪遊戲"""
		
		pre_check = await self.game_command_pre_check(interaction)
		if not pre_check:
			return
			
		title = game.question_set["title"]
		await interaction.response.send_message(f"{interaction.user.name} 重新開始了一輪 [{title}] 的猜歌遊戲！\n遊戲即將開始...")
		# 倒數 3 秒
		await asyncio.sleep(3)
		# 重置遊戲進度，開始播放第一題
		game.reset_progress()
		await self.init_question(game)
	
	# =========================================================================================

	async def check_auto_stop(self):
		for guild in self.bot.guilds:
			for vc in guild.voice_channels:
				if len(vc.members) == 1 and self.bot.user in vc.members:
					await vc.guild.voice_client.disconnect()
					if guild.id in self.games:
						del self.games[guild.id]
		
	@commands.command()
	async def sync(self, ctx) -> None:
		fmt = await ctx.bot.tree.sync()
		await ctx.send(f"Synced {len(fmt)} commands")



async def setup(bot):
	await bot.add_cog(SongGuesser(bot))