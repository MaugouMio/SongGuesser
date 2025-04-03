# This example requires the 'message_content' privileged intent to function.

import asyncio, functools
import json, os, random

import discord
from yt_dlp import YoutubeDL
from pydub import AudioSegment

from discord.ext import commands
from discord import app_commands

from cogs.format_checker import *

ytdlp_format_options = {
	'format': 'bestaudio',
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

ytdlp_options = dict()
class YTDLSource(discord.PCMVolumeTransformer):
	def __init__(self, source, *, volume=0.5):
		super().__init__(source, volume)

	@classmethod
	async def load_from_url(cls, url, parts, guild_id, *, loop=None):
		directory = f"temp/{guild_id}"
		if guild_id not in ytdlp_options:
			if not os.path.exists(directory):
				os.mkdir(directory)
				
			options = ytdlp_format_options.copy()
			options["outtmpl"] = f"{directory}/main.%(ext)s"
			ytdlp_options[guild_id] = options
		
		# remove old files
		for file in os.listdir(directory):
			os.remove(os.path.join(directory, file))
		
		with YoutubeDL(ytdlp_options[guild_id]) as ytdl:
			loop = loop or asyncio.get_event_loop()
			data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=True))
			filename = ytdl.prepare_filename(data)
		
		song = AudioSegment.from_file(filename, filename[(filename.find('.') + 1):])
		for i in range(len(parts)):
			part = parts[i]
			song[part[0]:part[1]].export(f"{directory}/{i}", format="mp3")

	@classmethod
	async def get_part(cls, part, guild_id):
		filename = f"temp/{guild_id}/{part}"
		return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options))



class GameStep:
	IDLE = 0		# 物件初始狀態
	WAITING = 1		# 遊戲剛開始還沒出題，或是已經結算完的狀態
	PLAYING = 2		# 出完題目正在等待玩家回答的狀態
	STOPPED = 3		# 被強制結束，但記憶體還沒被清乾淨的狀態

class GameData:
	def __init__(self, guild_id):
		self.guild_id = guild_id
		
		self.channel = None
		self.text_channel = None
		self.voice_client = None
		
		# settings
		self.one_guess_per_part = False
		
		# game progress
		self.step = GameStep.IDLE
		self.question_set = None
		self.current_question_idx = 0
		self.player_scores = dict()
		
		# question progress
		self.current_question_part = 0
		self.guessed_players = set()
		self.answer_guessed = False
	
	def reset_progress(self):
		self.current_question_idx = 0
		if self.question_set:
			random.shuffle(self.question_set["questions"])
		self.player_scores.clear()
			
		self.reset_question()
	
	def reset_question(self):
		self.current_question_part = 0
		self.guessed_players.clear()
		self.answer_guessed = None
		
	@staticmethod
	def initialize_question_set(question_set):
		result = validateQuestionFormat(question_set)
		if result != FormatErrorCode.OK:
			return result
		
		# generate candidate answer set
		candidate_set = set()
		for option in question_set["misleadings"]:
			candidate_set.add(option.lower())
		for question in question_set["questions"]:
			question_candidate_set = set()
			for candidate in question["candidates"]:
				candidate_set.add(candidate.lower())
				question_candidate_set.add(candidate.lower())
			question["candidates"] = question_candidate_set
		question_set["candidates"] = candidate_set
		
		return 0
	
class SongGuesser(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.games = dict()	 # <Guild, GameData>
	
	async def on_play_finished(self, e, game, message):
		if game.step != GameStep.PLAYING:
			return
			
		if e:
			print(f"[{game.guild_id}] Play question {game.current_question_idx + 1} part {game.current_question_part + 1} error: {e}")
		await message.edit(content=f"第 {game.current_question_idx + 1} 題片段 {game.current_question_part + 1} 播放完畢，快用 `/猜` 指令搶答吧！")
		
	async def play_part(self, game):
		if game.step != GameStep.PLAYING:
			return
			
		if game.voice_client.is_playing():
			game.voice_client.stop()
			
		source = await YTDLSource.get_part(game.current_question_part, game.guild_id)
		message = await game.text_channel.send(f"正在播放第 {game.current_question_idx + 1} 題片段 {game.current_question_part + 1}，使用 `/猜` 指令進行搶答")
		await asyncio.sleep(2)
		game.voice_client.play(source, after=lambda e, game=game, message=message: asyncio.run_coroutine_threadsafe(self.on_play_finished(e, game, message), self.bot.loop))
	
	async def init_question(self, game):
		if game.step != GameStep.PLAYING:
			return
			
		idx = game.current_question_idx
		vid = game.question_set["questions"][idx]["vid"]
		await YTDLSource.load_from_url(f"https://www.youtube.com/watch?v={vid}", game.question_set["questions"][idx]["parts"], game.guild_id, loop=self.bot.loop)
		game.reset_question()
		await self.play_part(game)
		
	async def next_question(self, interaction, current_question_idx = -1, button = None):
		game = await self.game_command_pre_check(interaction)
		if not game:
			return
		
		if button:
			button.disabled = True
			await interaction.response.edit_message(view=button.view)
		
		# 使用者按按鈕的時候，題目可能已經更換了
		if game.current_question_idx != current_question_idx:
			return
			
		if game.current_question_idx + 1 >= len(game.question_set["questions"]):
			await self.settle_game(interaction)
			return
			
		game.current_question_idx += 1
		await self.init_question(game)
		
	async def settle_game(self, interaction, button = None):
		game = await self.game_command_pre_check(interaction)
		if not game:
			return
		
		if button:
			button.disabled = True
			await interaction.response.edit_message(view=button.view)
			
		game.step = GameStep.WAITING
		
		end_hint = "\n可以使用 `/重新開始` 指令再玩一次\n或用 `/開始遊戲` 指令遊玩其它題庫"
		if len(game.player_scores) == 0:
			await game.text_channel.send("## 遊戲結束！沒有玩家有分數" + end_hint)
			return
			
		result = sorted(game.player_scores.items(), key=lambda item: item[1], reverse=True)
		result_text = [ f"{i+1}. {item[0].name} - {item[1]} 分" for i, item in enumerate(result) ]
		await game.text_channel.send("## 遊戲結束！\n> ### 排行榜：\n> " + "\n> ".join(result_text) + end_hint)
	
	# =========================================================================================

	@app_commands.command(name = "開始遊戲")
	async def start(self, interaction, attachment: discord.Attachment):
		"""上傳題庫，開始一場猜歌遊戲"""
		
		if interaction.guild.id not in self.games:
			self.games[interaction.guild.id] = GameData(interaction.guild.id)
		game = self.games[interaction.guild.id]
		
		if game.step == GameStep.PLAYING:
			await interaction.response.send_message(f"當前伺服器已在 <#{game.channel.id}> 進行遊戲，請先使用 `/結束遊戲` 指令中斷再試", ephemeral=True)
			return
		
		if not interaction.user.voice:
			await interaction.response.send_message(f"你必須在語音頻道內才能開啟一場遊戲", ephemeral=True)
			return
			
		try:
			data = await attachment.read()
			question_set = json.loads(data.decode("utf8"))
			initialize_result = GameData.initialize_question_set(question_set)
			if initialize_result != 0:
				await interaction.response.send_message(f"題庫檔案 {attachment.filename} 的格式不符，無法開始遊戲 (錯誤代碼: {initialize_result})", ephemeral=True)
				return
			game.question_set = question_set
		except:
			await interaction.response.send_message(f"上傳題庫檔案 {attachment.filename} 時發生錯誤，請檢查檔案內容是否正確", ephemeral=True)
			
		voice_client = interaction.guild.voice_client
		if voice_client is None:
			await interaction.user.voice.channel.connect()
			voice_client = interaction.guild.voice_client
		else:
			if voice_client.is_playing():
				voice_client.stop()
			await voice_client.move_to(interaction.user.voice.channel)
			
		text_channel = self.bot.get_channel(interaction.channel.id)
		
		game.channel = interaction.user.voice.channel
		game.text_channel = text_channel
		game.voice_client = voice_client
		game.step = GameStep.WAITING
		
		title = game.question_set["title"]
		author = game.question_set["author"]
		await interaction.response.send_message(f"{interaction.user.name} 開始了 __**{title} (by {author})**__ 的猜歌遊戲\n加入 <#{game.channel.id}> 頻道一起遊玩吧！")
		
		#倒數後直接開始第一題
		message = await game.text_channel.send("遊戲將於 5 秒後開始...")
		for i in range(4, -1, -1):
			await asyncio.sleep(1)
			if game.step == GameStep.STOPPED:
				return
			
			if i > 0:
				await message.edit(content=f"遊戲將於 {i} 秒後開始...")
			else:
				await message.edit(content=f"遊戲即將開始...")
		
		game.step = GameStep.PLAYING
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
		game.step = GameStep.STOPPED
		await interaction.response.send_message(f"已中止在 <#{game.channel.id}> 舉行的猜歌遊戲")
		del self.games[interaction.guild.id]
		
	# =========================================================================================
	
	async def game_command_pre_check(self, interaction, *, ignore_step = False):
		if interaction.guild.id not in self.games:
			await interaction.response.send_message("當前伺服器沒有舉行中的猜歌遊戲", ephemeral=True)
			return None
		
		game = self.games[interaction.guild.id]
		if not ignore_step and game.step != GameStep.PLAYING:
			await interaction.response.send_message("遊戲並未進行中，無法使用遊戲指令", ephemeral=True)
			return None
			
		if not interaction.user.voice or interaction.user.voice.channel != game.channel:
			await interaction.response.send_message(f"你必須在遊戲進行中的 <#{game.channel.id}> 頻道才能使用遊戲指令", ephemeral=True)
			return None
			
		if interaction.channel != game.text_channel:
			await interaction.response.send_message(f"你必須在遊戲進行中的 <#{game.text_channel.id}> 頻道才能使用遊戲指令", ephemeral=True)
			return None
		
		return game
	
	@app_commands.command(name = "下一題")
	async def question(self, interaction):
		"""[遊戲指令] 從題庫中隨機出題"""
		
		game = await self.game_command_pre_check(interaction)
		if not game:
			return
		
		idx = game.current_question_idx
		if not game.answer_guessed:
			# 沒有人答出來過要跳確認訊息
			view = discord.ui.View(timeout = 30)
			button = discord.ui.Button(label = "確定")
			button.callback = functools.partial(self.next_question, current_question_idx=idx, button=button)
			view.add_item(button)
			await interaction.response.send_message("還沒有人猜出答案，確定要跳過嗎？", view = view)
			return
			
		await interaction.response.send_message("已成功執行指令，請稍候")
		await self.next_question(interaction, idx)
	
	@app_commands.command(name = "更多片段")
	async def hint(self, interaction):
		"""[遊戲指令] 播放當前題目下一個音樂片段"""
		
		game = await self.game_command_pre_check(interaction)
		if not game:
			return
			
		if game.current_question_part + 1 >= len(game.question_set["questions"][game.current_question_idx]["parts"]):
			await interaction.response.send_message("已經沒有更多歌曲片段了！", ephemeral=True)
			return
			
		await interaction.response.send_message("已成功執行指令，請稍候")
		game.current_question_part += 1
		await self.play_part(game)
	
	@app_commands.command(name = "重播片段")
	async def again(self, interaction):
		"""[遊戲指令] 重新播放當前的音樂片段"""
		
		game = await self.game_command_pre_check(interaction)
		if not game:
			return
			
		await interaction.response.send_message("已成功執行指令，請稍候")
		await self.play_part(game)
	
	@app_commands.command(name = "猜")
	async def guess(self, interaction, answer: str):
		"""[遊戲指令] 猜測當前題目的答案"""
		
		game = await self.game_command_pre_check(interaction)
		if not game:
			return
		
		if game.answer_guessed:
			await interaction.response.send_message("已經有人猜出這題答案了，下一題再加油吧！", ephemeral=True)
			return
		
		if game.one_guess_per_part and interaction.user in game.guessed_players:
			await interaction.response.send_message("你在這個片段已經猜過了，請等下個片段播放後再試", ephemeral=True)
			return
			
		game.guessed_players.add(interaction.user)
		
		if answer not in game.question_set["candidates"]:
			# 讓他看相關的選項
			related_list = []
			tokens = answer.split()
			over_10_candidates = False
			for candidate in game.question_set["candidates"]:
				if all(candidate.find(token.lower()) >= 0 for token in tokens):
					if len(related_list) >= 10:
						over_10_candidates = True
						break
					related_list.append(candidate)
			
			if len(related_list) == 0:
				await interaction.response.send_message("沒有任何符合或相似的選項，建議使用更廣泛的關鍵字", ephemeral=True)
			else:
				hint_text = "沒有符合的選項，以下是相關的選項列表"
				for option in related_list:
					hint_text += f"\n- {option}"
				if over_10_candidates:
					hint_text += "\n還有更多關聯選項，建議使用更精確的關鍵字"
				await interaction.response.send_message(hint_text, ephemeral=True)
			return
			
		idx = game.current_question_idx
		if answer in game.question_set["questions"][idx]["candidates"]:
			vid = game.question_set["questions"][idx]["vid"]
			await interaction.response.send_message(f"⭕ {interaction.user.name} 猜：{answer}\n成功獲得一分！\n使用 `/下一題` 指令繼續遊戲\nhttps://www.youtube.com/watch?v={vid}")
			game.answer_guessed = True
			
			if interaction.user not in game.player_scores:
				game.player_scores[interaction.user] = 1
			else:
				game.player_scores[interaction.user] += 1
		else:
			await interaction.response.send_message(f"❌ {interaction.user.name} 猜：{answer}")
	
	@app_commands.command(name = "結算")
	async def settle(self, interaction):
		"""[遊戲指令] 中止當前的遊戲並進行結算"""
		
		game = await self.game_command_pre_check(interaction)
		if not game:
			return
		
		if not game.answer_guessed:
			# 當前題目還沒有人猜到要跳確認訊息
			view = discord.ui.View(timeout = 30)
			button = discord.ui.Button(label = "確定")
			button.callback = functools.partial(self.settle_game, button=button)
			view.add_item(button)
			await interaction.response.send_message("現在進行中的題目還沒有人猜出來，確定要直接結算嗎？", view = view)
			return
			
		await interaction.response.send_message("已成功執行指令，請稍候")
		await self.settle_game(interaction)
	
	@app_commands.command(name = "重新開始")
	async def restart(self, interaction):
		"""[遊戲指令] 以目前的題庫重新進行一輪遊戲"""
		
		game = await self.game_command_pre_check(interaction, ignore_step=True)
		if not game:
			return
			
		title = game.question_set["title"]
		await interaction.response.send_message(f"{interaction.user.name} 重新開始了一輪 __**{title}**__ 的猜歌遊戲！\n遊戲即將開始...")
		# 倒數 3 秒
		await asyncio.sleep(3)
		# 重置遊戲進度，開始播放第一題
		game.step = GameStep.PLAYING
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