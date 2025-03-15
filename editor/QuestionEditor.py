import sys, os, asyncio, json, re, pickle
sys.path.insert(0, '..')

import urllib
from urllib.parse import urlparse
from urllib.parse import parse_qs

from youtube_dl import youtube_dl
from pydub import AudioSegment

from PyQt6 import uic
from PyQt6 import QtWidgets, QtGui
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import Qt, QUrl, QSize, QTime

WINDOW_TITLE = "猜歌機器人題庫編輯器"
YOUTUBE_ERROR_MSG = "無法載入指定的 Youtube 影片"

QUESTION_SET_TEMPLATE = {
	"title": "我的題庫",
	"author": "我的暱稱",
	"questions": [],
	"misleadings": []
}
QUESTION_OBJ_TEMPLATE = {
	"title": "",
	"vid": "",
	"parts": [],
	"candidates": []
}



def getTimeText(t):
	minutes = t // 60000
	seconds = (t // 1000) % 60
	ms = t % 1000
	return f"{minutes}:{seconds:02d}.{ms:03d}"
	
def getQTime(t):
	minutes = t // 60000
	seconds = (t // 1000) % 60
	ms = t % 1000
	return QTime(0, minutes, seconds, ms)

# clickable slider
class Slider(QtWidgets.QSlider):
	def mousePressEvent(self, e):
		if e.button() == Qt.MouseButton.LeftButton:
			e.accept()
			x = e.pos().x()
			value = (self.maximum() - self.minimum()) * x // self.width() + self.minimum()
			self.sliderMoved.emit(value)
		return super().mousePressEvent(e)

class QuestionEditor(QtWidgets.QMainWindow):
	def __init__(self):
		super().__init__()
		uic.loadUi("main.ui", self)
		
		# cache 處理
		if not os.path.exists("cache"):
			os.mkdir("cache")
		if os.path.isfile("cache/data.pickle"):
			with open("cache/data.pickle", "rb") as f:
				self.youtube_cache = pickle.load(f)
		else:
			self.youtube_cache = dict()
		# 音檔 cache 紀錄
		self.youtube_audio_cache = set()
		for file in os.listdir("cache"):
			if file != "data.pickle":
				self.youtube_audio_cache.add(file)
		
		# 確認是否先存檔的 message box
		self.check_save = QtWidgets.QMessageBox(self)
		self.check_save.setWindowTitle(WINDOW_TITLE)
		self.check_save.setIcon(QtWidgets.QMessageBox.Icon.Information)
		self.check_save.setText("要儲存當前檔案的變更嗎？")
		self.check_save.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No | QtWidgets.QMessageBox.StandardButton.Cancel)
		self.check_save.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Yes)
		
		# 輸入 youtube url 的 dialog
		self.youtube_url_dialog = QtWidgets.QInputDialog()
		self.youtube_url_dialog.setInputMode(QtWidgets.QInputDialog.InputMode.TextInput)
		self.youtube_url_dialog.setWindowTitle(WINDOW_TITLE)
		self.youtube_url_dialog.setLabelText("輸入 Youtube 網址：")
		self.youtube_url_dialog.setFixedSize(480, 120)
		
		# 提示訊息
		self.message_box = QtWidgets.QMessageBox(self)

		self.question_set = QUESTION_SET_TEMPLATE.copy()
		self.question_vid_set = set()  # 紀錄當前題庫的影片 ID 列表
		self.current_detail_vid = ""  # 當前右邊詳細資訊對應的題目影片 ID
		self.file_path = None
		self.dirty_flag = False
		
		self.dragPositionWasPlaying = False
		self.auto_pause_time = -1
		
		self.initUI()

	def initUI(self):
		# 選單
		self.action_new.triggered.connect(self.newFile)
		self.action_load.triggered.connect(self.loadFile)
		self.action_save.triggered.connect(self.save)
		self.action_save_as.triggered.connect(self.saveAs)
		
		# 題目列表
		self.question_list_widget.itemClicked.connect(self.updateQuestionDetail)
		self.add_question_btn.clicked.connect(self.addQuestion)
		self.del_question_btn.clicked.connect(self.delQuestion)
		
		# 音樂播放器
		self.media_player = QMediaPlayer()
		self.audio_output = QAudioOutput()
		self.audio_output.setVolume(self.volume_slider.value() / 100)
		self.media_player.setAudioOutput(self.audio_output)

		self.play_button.clicked.connect(self.playPause)
		self.test_part_button.clicked.connect(self.playPart)

		self.position_slider = Slider(Qt.Orientation.Horizontal)
		self.position_slider.setRange(0, 0)
		self.position_slider.sliderPressed.connect(self.beginDragPosition)
		self.position_slider.sliderMoved.connect(self.setPosition)
		self.position_slider.sliderReleased.connect(self.endDragPosition)
		self.frame_audio_player.addWidget(self.position_slider)
		
		self.volume_slider.valueChanged.connect(self.setVolume)

		self.media_player.positionChanged.connect(self.positionChanged)
		self.media_player.durationChanged.connect(self.durationChanged)
		self.media_player.playbackStateChanged.connect(self.playbackStateChanged)
		
		self.set_begin_btn.clicked.connect(self.setBeginTime)
		self.begin_time.setTime(QTime(0, 0))
		self.begin_time.userTimeChanged.connect(self.beginTimeChanged)
		self.set_end_btn.clicked.connect(self.setEndTime)
		self.end_time.setTime(QTime(0, 0))
		self.end_time.userTimeChanged.connect(self.endTimeChanged)
		
		# 片段列表
		self.part_list_widget.itemClicked.connect(self.updateQuestionPartSetting)

		self.updatePage()
		self.show()
	
	def keyPressEvent(self, event):
		if event.key() == Qt.Key.Key_S:
			modifiers = QtWidgets.QApplication.keyboardModifiers()
			if modifiers == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
				self.saveAs()
			elif modifiers == Qt.KeyboardModifier.ControlModifier:
				self.save()
		elif event.key() == Qt.Key.Key_N:
			modifiers = QtWidgets.QApplication.keyboardModifiers()
			if modifiers == Qt.KeyboardModifier.ControlModifier:
				self.newFile()
		elif event.key() == Qt.Key.Key_O:
			modifiers = QtWidgets.QApplication.keyboardModifiers()
			if modifiers == Qt.KeyboardModifier.ControlModifier:
				self.loadFile()
	
	def closeEvent(self, event):
		do_close = True
		if self.dirty_flag:
			result = self.check_save.exec()
			if result == QtWidgets.QMessageBox.StandardButton.Yes:
				self.save()
			elif result == QtWidgets.QMessageBox.StandardButton.Cancel:
				do_close = False
		
		if do_close:
			with open("cache/data.pickle", "wb") as f:
				pickle.dump(self.youtube_cache, f)
			event.accept()
		else:
			event.ignore()
		
	# ====================================================================================================

	def getYoutubeInfo(self, vid):
		if vid in self.youtube_cache:
			return self.youtube_cache[vid]
			
		url = f"https://noembed.com/embed?url=https://www.youtube.com/watch?v={vid}"
		try:
			data = json.loads(urllib.request.urlopen(url).read().decode("utf8"))
			if "error" in data:
				return None
		except:
			return None
			
		info = {
			"title": data["title"],
			"author": data["author_name"],
			"thumbnail": data["thumbnail_url"]
		}
		self.youtube_cache[vid] = info
		return info

	def downloadYoutube(self, vid):
		if vid in self.youtube_audio_cache:
			return
			
		url = f"https://www.youtube.com/watch?v={vid}"
		ytdl_format_options = {
			'format': 'bestaudio/best',
			'outtmpl': f'cache/{vid}',
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
		ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
		ytdl.download([url])
		self.youtube_audio_cache.add(vid)

	def getYoutubeVideoID(self, url):
		youtube_regex = (r'(https?://)?(www\.)?'
						 '(youtube|youtu|youtube-nocookie)\.(com|be)/'
						 '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')

		youtube_match = re.match(youtube_regex, url)
		if youtube_match:
			return youtube_match.group(6)
		return ""
	
	def getCurrentQuestion(self):
		question_list = self.question_set["questions"]
		idx = self.question_list_widget.currentRow()
		if len(question_list) == 0 or idx >= len(question_list):
			return None
		return question_list[idx]
	
	def getCurrentQuestionPart(self):
		question = self.getCurrentQuestion()
		if not question:
			return None
			
		question_parts = question["parts"]
		idx = self.part_list_widget.currentRow()
		if len(question_parts) == 0 or idx >= len(question_parts):
			return None
			
		return question_parts[idx]
		
	# ====================================================================================================
		
	def updateWindowTitle(self):
		if self.file_path:
			save_note = self.dirty_flag and "[*]" or ""
			self.setWindowTitle(f"{WINDOW_TITLE} - {os.path.basename(self.file_path)}" + save_note)
		else:
			self.setWindowTitle(f"{WINDOW_TITLE} - New File")
		
	def updateQuestionList(self):
		question_list = self.question_set["questions"]
		self.question_list_title.setText(f"題目列表 ({len(question_list)})")
		for i in range(len(question_list)):
			if self.question_list_widget.count() <= i:
				item = QtWidgets.QListWidgetItem()
				self.question_list_widget.addItem(item)
			else:
				item = self.question_list_widget.item(i)
				
			item.setText(question_list[i]["title"])
			item.setHidden(False)
				
		for i in range(len(question_list), self.question_list_widget.count()):
			item = self.question_list_widget.item(i)
			item.setHidden(True)
	
	def updateQuestionPartList(self):
		question = self.getCurrentQuestion()
		if not question:
			return
		
		question_parts = question["parts"]
		for i in range(len(question_parts)):
			if self.part_list_widget.count() <= i:
				item = QtWidgets.QListWidgetItem(str(i + 1))
				item.setSizeHint(QSize(25, 25))
				item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
				self.part_list_widget.addItem(item)
			else:
				item = self.part_list_widget.item(i)
				
			item.setHidden(False)
				
		for i in range(len(question_parts), self.part_list_widget.count()):
			item = self.part_list_widget.item(i)
			item.setHidden(True)
		
	def updateQuestionPartSetting(self):
		question = self.getCurrentQuestion()
		if not question:
			return
		
		question_part = self.getCurrentQuestionPart()
		if not question_part:
			return
		
		self.begin_time.setTime(getQTime(question_part[0]))
		self.end_time.setTime(getQTime(question_part[1]))
	
	def updateQuestionDetail(self):
		question = self.getCurrentQuestion()
		if not question:
			self.question_detail_page.setEnabled(False)
			return
		
		vid = question["vid"]
		if vid == self.current_detail_vid:
			return
		self.current_detail_vid = vid
			
		# 先重置播放器
		self.media_player.setSource(QUrl())
		self.play_button.setText("▶")
		
		self.question_detail_page.setEnabled(True)
		
		info = self.getYoutubeInfo(vid)
		# 更新右邊資訊
		self.youtube_title.setText(info["title"])
		self.youtube_author.setText(info["author"])
		self.youtube_url.setText(f"https://www.youtube.com/watch?v={vid}")
		
		data = urllib.request.urlopen(info["thumbnail"]).read()
		pixmap = QtGui.QPixmap()
		pixmap.loadFromData(data)
		pixmap = pixmap.scaled(self.youtube_thumbnail.size(), Qt.AspectRatioMode.KeepAspectRatio)
		self.youtube_thumbnail.setPixmap(pixmap)
		
		self.updateDurationLabel(info.get("duration", None))
		self.media_player.setPosition(0)
		
		self.updateQuestionPartList()
		self.part_list_widget.setCurrentRow(0)
		self.updateQuestionPartSetting()
	
	def updatePage(self):
		# 更新整個畫面內容
		self.updateQuestionList()
		self.updateQuestionDetail()
		self.updateWindowTitle()
	
	def newFile(self):
		if self.dirty_flag:
			result = self.check_save.exec()
			if result == QtWidgets.QMessageBox.StandardButton.Yes:
				self.save()
			elif result == QtWidgets.QMessageBox.StandardButton.Cancel:
				return
				
		self.question_set = QUESTION_SET_TEMPLATE.copy()
		self.question_vid_set.clear()
		self.current_detail_vid = ""
		self.file_path = None
		self.dirty_flag = False
		
		self.updatePage()
	
	def loadFile(self):
		if self.dirty_flag:
			result = self.check_save.exec()
			if result == QtWidgets.QMessageBox.StandardButton.Yes:
				self.save()
			elif result == QtWidgets.QMessageBox.StandardButton.Cancel:
				return
				
		file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "載入檔案", "", "JSON Files(*.json)")
		if file_path == "":
			return
			
		with open(file_path, "r", encoding="utf8") as f:
			question_set = json.loads(f.read())
		# TODO: 檢查檔案格式，不合理跳警告並 return
		
		self.question_set = question_set
		self.question_vid_set.clear()
		for question in question_set["questions"]:
			self.question_vid_set.add(question["vid"])
		self.current_detail_vid = ""
		self.file_path = file_path
		self.dirty_flag = False
		
		self.question_list_widget.setCurrentRow(0)
		self.updatePage()
	
	def saveReal(self):
		# TODO: 檢查檔案格式，不合理跳警告
		with open(self.file_path, "w") as f:
			f.write(json.dumps(self.question_set))
			
		self.dirty_flag = False
		self.updateWindowTitle()
	
	def saveAs(self):
		file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "另存新檔", "", "JSON Files(*.json)")
		if file_path == "":
			return
			
		self.file_path = file_path
		self.saveReal()
	
	def save(self):
		if self.file_path:
			if self.dirty_flag:
				self.saveReal()
		else:
			self.saveAs()
		
	# ====================================================================================================
	
	def addQuestion(self):
		if self.youtube_url_dialog.exec() != QtWidgets.QInputDialog.DialogCode.Accepted:
			return
			
		url = self.youtube_url_dialog.textValue()
		vid = self.getYoutubeVideoID(url)
		if not vid:
			self.message_box.critical(self, WINDOW_TITLE, YOUTUBE_ERROR_MSG)
			return
		
		if vid in self.question_vid_set:
			for i, question in enumerate(self.question_set["questions"]):
				if question["vid"] == vid:
					self.question_list_widget.setCurrentRow(i)
					self.updateQuestionDetail()
					break
			return
		
		info = self.getYoutubeInfo(vid)
		if not info:
			self.message_box.critical(self, WINDOW_TITLE, YOUTUBE_ERROR_MSG)
			return
		
		question = QUESTION_OBJ_TEMPLATE.copy()
		question["title"] = info["title"]
		question["vid"] = vid
		question["parts"].append([0, 3000])  # 預設第一個片段是前 3 秒
		
		target_idx = len(self.question_set["questions"])
		self.question_set["questions"].append(question)
		self.question_vid_set.add(vid)
		self.dirty_flag = True
		
		# 點到新增的那個項目上
		self.updateQuestionList()
		self.question_list_widget.setCurrentRow(target_idx)
		self.updateQuestionDetail()
	
	def delQuestion(self):
		question_list = self.question_set["questions"]
		if len(question_list) == 0:
			return
		
		idx = self.question_list_widget.currentRow()
		if idx >= len(question_list):
			return
		
		self.question_vid_set.remove(question_list[idx]["vid"])
		del question_list[idx]
		self.updatePage()
		
	# ====================================================================================================
	
	def checkDownloadBeforePlay(self):
		if self.media_player.source().isEmpty():
			question = self.getCurrentQuestion()
			if not question:
				return
			
			vid = question["vid"]
			self.downloadYoutube(vid)
			self.media_player.setSource(QUrl.fromLocalFile(f"cache/{vid}"))

	def playPause(self):
		# 先下載並載入音檔
		self.checkDownloadBeforePlay()
		# 手動按播放或暫停時中斷試聽
		self.auto_pause_time = -1
		
		if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
			self.media_player.pause()
		else:
			self.media_player.play()

	def playPart(self):
		question_part = self.getCurrentQuestionPart()
		if not question_part:
			return
			
		# 先下載並載入音檔
		self.checkDownloadBeforePlay()
		
		self.media_player.play()
		self.media_player.setPosition(question_part[0])
		self.play_button.setText("∎∎")
		
		self.auto_pause_time = question_part[1]
	
	def playbackStateChanged(self, newState):
		if newState == QMediaPlayer.PlaybackState.PlayingState:
			self.play_button.setText("∎∎")
		else:
			self.play_button.setText("▶")

	def positionChanged(self, position):
		if self.auto_pause_time >= 0 and position >= self.auto_pause_time:
			self.media_player.pause()
			
		self.position_slider.setValue(position)
		self.updateTimeLabel()
	
	def updateDurationLabel(self, duration):
		if duration:
			self.duration_label.setText(getTimeText(duration))
		else:
			self.duration_label.setText("--:--.---")

	def durationChanged(self, duration):
		question = self.getCurrentQuestion()
		if not question:
			return
		
		vid = question["vid"]
		# 更新 cache 音樂長度
		self.youtube_cache[vid]["duration"] = duration
		
		# 不特別限制使用者設定超過最大的時間，不然還要考慮切歌的時候會不會被上限修正影響到
		# new_max_time = getQTime(duration)
		# self.begin_time.setMaximumTime(new_max_time)
		# self.end_time.setMaximumTime(new_max_time)
		
		self.position_slider.setRange(0, duration)
		
		self.updateDurationLabel(duration)
		self.updateTimeLabel()
	
	def beginDragPosition(self):
		self.dragPositionWasPlaying = self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
		self.media_player.pause()

	def setPosition(self, position):
		self.media_player.setPosition(position)
	
	def endDragPosition(self):
		if self.dragPositionWasPlaying:
			self.media_player.play()

	def updateTimeLabel(self):
		position = self.media_player.position()
		self.position_label.setText(getTimeText(position))

	def setVolume(self, volume):
		self.audio_output.setVolume(volume / 100)

	def setBeginTime(self):
		nowTime = getQTime(self.media_player.position())
		self.begin_time.setTime(nowTime)

	def beginTimeChanged(self, qtime):
		question_part = self.getCurrentQuestionPart()
		if not question_part:
			return
		
		question_part[0] = qtime.minute() * 60000 + qtime.second() * 1000 + qtime.msec()
		self.dirty_flag = True

	def setEndTime(self):
		nowTime = getQTime(self.media_player.position())
		self.end_time.setTime(nowTime)

	def endTimeChanged(self, qtime):
		question_part = self.getCurrentQuestionPart()
		if not question_part:
			return
		
		question_part[1] = qtime.minute() * 60000 + qtime.second() * 1000 + qtime.msec()
		self.dirty_flag = True

if __name__ == '__main__':
	app = QtWidgets.QApplication(sys.argv)
	player = QuestionEditor()
	sys.exit(app.exec())
