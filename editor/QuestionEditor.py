import sys, os, json, re, pickle, copy
sys.path.insert(0, '..')

import urllib
from urllib.parse import urlparse
from urllib.parse import parse_qs

from youtube_dl import youtube_dl
from pytube import Playlist

from PyQt6 import uic
from PyQt6 import QtWidgets, QtGui
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import Qt, QCoreApplication, QUrl, QSize, QTime, QRect

WINDOW_TITLE = "猜歌機器人題庫編輯器"
YOUTUBE_ERROR_MSG = "無法載入指定的 Youtube 影片"
PLAYLIST_ERROR_MSG = "無法載入指定的 Youtube 播放清單"
NEW_TEMP_ANSWER = "(雙擊編輯答案)"

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



class ModifyRecord:
	def __init__(self, path, before, after):
		self.path = path
		self.before = copy.deepcopy(before)
		self.after = copy.deepcopy(after)



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



# 參考 misleading_edit.ui 生成的程式碼調整
class MisleadingAnsWindow(QtWidgets.QWidget):
	def __init__(self, addCallback, delCallback, editCallback, undo, redo):
		super().__init__()
		
		self.resize(480, 300)
		self.setMinimumSize(480, 300)
		self.setMaximumSize(480, 300)
		self.setWindowTitle(WINDOW_TITLE)
		
		self.title = QtWidgets.QLabel(self)
		self.title.setGeometry(QRect(10, 10, 141, 21))
		font = QtGui.QFont()
		font.setPointSize(12)
		font.setBold(True)
		self.title.setFont(font)
		self.title.setText(QCoreApplication.translate("MisleadingAnsWindow", u"\u8aa4\u5c0e\u7528\u7b54\u6848\u5217\u8868", None))
		
		self.misleading_ans_list = QtWidgets.QListWidget(self)
		self.misleading_ans_list.setGeometry(QRect(10, 40, 461, 221))
		self.misleading_ans_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
		self.misleading_ans_list.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
		self.misleading_ans_list.itemChanged.connect(self.editMisleadingAnswer)
		
		self.del_mis_ans_btn = QtWidgets.QPushButton(self)
		self.del_mis_ans_btn.setGeometry(QRect(245, 270, 75, 23))
		self.del_mis_ans_btn.clicked.connect(self.delMisleadingAnswer)
		self.del_mis_ans_btn.setText(QCoreApplication.translate("MisleadingAnsWindow", u"\u522a\u9664", None))
		
		self.add_mis_ans_btn = QtWidgets.QPushButton(self)
		self.add_mis_ans_btn.setGeometry(QRect(160, 270, 75, 23))
		self.add_mis_ans_btn.clicked.connect(self.addMisleadingAnswer)
		self.add_mis_ans_btn.setText(QCoreApplication.translate("MisleadingAnsWindow", u"\u65b0\u589e", None))
		
		self.onAddAnswer = addCallback
		self.onDeleteAnswer = delCallback
		self.onEditAnswer = editCallback
		self.undo = undo
		self.redo = redo
		
	def keyPressEvent(self, event):
		if event.key() == Qt.Key.Key_Delete:
			if self.misleading_ans_list.hasFocus():
				self.delMisleadingAnswer()
		elif event.key() == Qt.Key.Key_Z:
			modifiers = QtWidgets.QApplication.keyboardModifiers()
			if modifiers == Qt.KeyboardModifier.ControlModifier:
				self.undo()
		elif event.key() == Qt.Key.Key_Y:
			modifiers = QtWidgets.QApplication.keyboardModifiers()
			if modifiers == Qt.KeyboardModifier.ControlModifier:
				self.redo()
	
	# ==============================================================
	
	def updateMisleadingAnswerList(self, answers):
		for i in range(len(answers)):
			if self.misleading_ans_list.count() <= i:
				item = QtWidgets.QListWidgetItem(answers[i])
				item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
				self.misleading_ans_list.addItem(item)
			else:
				item = self.misleading_ans_list.item(i)
				item.setText(answers[i])
				
			item.setHidden(False)
				
		for i in range(len(answers), self.misleading_ans_list.count()):
			item = self.misleading_ans_list.item(i)
			item.setHidden(True)
		
	def addMisleadingAnswer(self):
		if self.onAddAnswer:
			answers = self.onAddAnswer()
			self.updateMisleadingAnswerList(answers)
			self.misleading_ans_list.scrollToItem(self.misleading_ans_list.item(len(answers) - 1))
			
	def delMisleadingAnswer(self):
		selected = self.misleading_ans_list.selectedItems()
		if len(selected) == 0:
			return
		
		selected_idx = [self.misleading_ans_list.row(item) for item in selected]
		# 要從後面開始刪才不會影響 index
		selected_idx.sort()
		
		if self.onDeleteAnswer:
			answers = self.onDeleteAnswer(selected_idx)
			if not answers:
				return
				
			self.misleading_ans_list.clearSelection()
			self.updateMisleadingAnswerList(answers)
			
	def editMisleadingAnswer(self, item):
		# 空字串不接受，顯示回原本內容
		if len(item.text()) == 0:
			return
			
		if self.onEditAnswer:
			idx = self.misleading_ans_list.row(item)
			answers = self.onEditAnswer(idx, item.text())
			if answers:
				self.updateMisleadingAnswerList(answers)

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
		
		# 確認是否匯入整個播放清單的 message box
		self.check_all_playlist = QtWidgets.QMessageBox(self)
		self.check_all_playlist.setWindowTitle(WINDOW_TITLE)
		self.check_all_playlist.setIcon(QtWidgets.QMessageBox.Icon.Information)
		self.check_all_playlist.setText("是否匯入整個播放清單？")
		self.check_all_playlist.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
		self.check_all_playlist.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
		
		# 提示訊息
		self.message_box = QtWidgets.QMessageBox(self)

		self.question_set = copy.deepcopy(QUESTION_SET_TEMPLATE)
		self.question_vid_set = set()  # 紀錄當前題庫的影片 ID 列表
		self.current_detail_vid = ""  # 當前右邊詳細資訊對應的題目影片 ID
		self.file_path = None
		
		self.need_reload_media = False
		self.dragPositionWasPlaying = False
		self.auto_pause_time = -1
		
		self.modify_record = []
		self.modify_record_idx = -1
		self.save_modify_record_idx = -1
		
		self.auto_select_qustion_idx = -1
		self.auto_select_qustion_part_idx = -1
		
		self.initUI()

	def initUI(self):
		# 選單
		self.action_new.triggered.connect(self.newFile)
		self.action_load.triggered.connect(self.loadFile)
		self.action_save.triggered.connect(self.save)
		self.action_save_as.triggered.connect(self.saveAs)
		
		# 誤導用答案編輯視窗
		self.misleading_ans_window = MisleadingAnsWindow(self.addMisleadingAnswer, self.delMisleadingAnswer, self.editMisleadingAnswer, self.undo, self.redo)
		self.edit_misleading_btn.clicked.connect(self.misleading_ans_window.show)
		
		# 題目列表
		self.question_list_widget.itemClicked.connect(self.updateQuestionDetail)
		self.add_question_btn.clicked.connect(self.addQuestion)
		self.del_question_btn.clicked.connect(self.delQuestion)
		
		# 答案列表
		self.add_ans_btn.clicked.connect(self.addValidAnswer)
		self.del_ans_btn.clicked.connect(self.delValidAnswer)
		self.valid_answer_list.itemChanged.connect(self.editValidAnswer)
		
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
		self.part_list_widget.horizontalScrollBar().setStyleSheet("QScrollBar{height:4px}")
		
		self.add_part_btn.clicked.connect(self.addQuestionPart)
		self.delete_part_btn.clicked.connect(self.delQuestionPart)
		self.move_left_btn.clicked.connect(self.movePartLeft)
		self.move_right_btn.clicked.connect(self.movePartRight)

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
		elif event.key() == Qt.Key.Key_Z:
			modifiers = QtWidgets.QApplication.keyboardModifiers()
			if modifiers == Qt.KeyboardModifier.ControlModifier:
				self.undo()
		elif event.key() == Qt.Key.Key_Y:
			modifiers = QtWidgets.QApplication.keyboardModifiers()
			if modifiers == Qt.KeyboardModifier.ControlModifier:
				self.redo()
		elif event.key() == Qt.Key.Key_Delete:
			if self.valid_answer_list.hasFocus():
				self.delValidAnswer()
	
	def closeEvent(self, event):
		do_close = True
		if self.isDirty():
			result = self.check_save.exec()
			if result == QtWidgets.QMessageBox.StandardButton.Yes:
				self.save()
			elif result == QtWidgets.QMessageBox.StandardButton.Cancel:
				do_close = False
		
		if do_close:
			if self.misleading_ans_window.isVisible():
				self.misleading_ans_window.hide()
				
			with open("cache/data.pickle", "wb") as f:
				pickle.dump(self.youtube_cache, f)
			event.accept()
		else:
			event.ignore()
		
	# ====================================================================================================
	
	def isDirty(self):
		return self.save_modify_record_idx != self.modify_record_idx
	
	def resetModifyRecord(self):
		self.modify_record.clear()
		self.modify_record_idx = -1
		self.save_modify_record_idx = -1
	
	def recordModify(self, path, *, before=None, after=None):
		if type(path[-1]) is not list and before == after:
			return
			
		del self.modify_record[(self.modify_record_idx + 1):]
		self.modify_record.append(ModifyRecord(path, before, after))
		
		if self.save_modify_record_idx > self.modify_record_idx:
			self.save_modify_record_idx = -1
		self.modify_record_idx += 1
		
		self.updateWindowTitle()
	
	def undo(self):
		if self.modify_record_idx < 0:
			return
		
		record = self.modify_record[self.modify_record_idx]
		self.modify_record_idx -= 1
		
		target = self.question_set
		for i in range(len(record.path) - 1):
			if record.path[i] == "questions":
				self.auto_select_qustion_idx = record.path[i + 1]
			elif record.path[i] == "parts":
				if type(record.path[i + 1]) is list:
					self.auto_select_qustion_part_idx = record.path[i + 1][0]
				else:
					self.auto_select_qustion_part_idx = record.path[i + 1]
			elif record.path[i] == "misleadings":
				self.misleading_ans_window.show()
			target = target[record.path[i]]
			
		if type(record.path[-1]) is list:  # means swap
			target[record.path[-1][0]], target[record.path[-1][1]] = target[record.path[-1][1]], target[record.path[-1][0]]
		elif record.before == None:
			if len(record.path) == 2 and record.path[0] == "questions":  # undo add question
				self.question_vid_set.remove(target[record.path[-1]]["vid"])
			del target[record.path[-1]]
		elif record.after == None:
			if len(record.path) == 2 and record.path[0] == "questions":  # undo remove question
				self.question_vid_set.add(record.before["vid"])
			target.insert(record.path[-1], copy.deepcopy(record.before))
		else:
			target[record.path[-1]] = copy.deepcopy(record.before)
			
		self.updatePage()
	
	def redo(self):
		if self.modify_record_idx + 1 >= len(self.modify_record):
			return
		
		record = self.modify_record[self.modify_record_idx + 1]
		self.modify_record_idx += 1
		
		target = self.question_set
		for i in range(len(record.path) - 1):
			if record.path[i] == "questions":
				self.auto_select_qustion_idx = record.path[i + 1]
			elif record.path[i] == "parts":
				if type(record.path[i + 1]) is list:
					self.auto_select_qustion_part_idx = record.path[i + 1][1]
				else:
					self.auto_select_qustion_part_idx = record.path[i + 1]
			elif record.path[i] == "misleadings":
				self.misleading_ans_window.show()
			target = target[record.path[i]]
			
		if type(record.path[-1]) is list:  # means swap
			target[record.path[-1][0]], target[record.path[-1][1]] = target[record.path[-1][1]], target[record.path[-1][0]]
		elif record.after == None:
			if len(record.path) == 2 and record.path[0] == "questions":  # redo remove question
				self.question_vid_set.remove(target[record.path[-1]]["vid"])
			del target[record.path[-1]]
		elif record.before == None:
			if len(record.path) == 2 and record.path[0] == "questions":  # redo add question
				self.question_vid_set.add(record.after["vid"])
			target.insert(record.path[-1], copy.deepcopy(record.after))
		else:
			target[record.path[-1]] = copy.deepcopy(record.after)
		
		self.updatePage()
		
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
	
	def getYoutubePlaylist(self, url):
		try:
			playlist = Playlist(url)
			return [ link.split("?v=")[1] for link in playlist ]
		except:
			return None

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
			return None, -1
		return question_list[idx], idx
	
	def getCurrentQuestionPart(self):
		question, qidx = self.getCurrentQuestion()
		if not question:
			return None, -1, -1
			
		question_parts = question["parts"]
		idx = self.part_list_widget.currentRow()
		if len(question_parts) == 0 or idx >= len(question_parts):
			return None, -1, -1
			
		return question_parts[idx], qidx, idx
		
	# ====================================================================================================
		
	def updateWindowTitle(self):
		if self.file_path:
			save_note = self.save_modify_record_idx != self.modify_record_idx and "[*]" or ""
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
		
		if self.auto_select_qustion_idx >= 0:
			if self.auto_select_qustion_idx >= len(question_list):
				self.auto_select_qustion_idx = len(question_list) - 1
			if self.question_list_widget.currentRow() != self.auto_select_qustion_idx and self.auto_select_qustion_part_idx < 0:
				self.auto_select_qustion_part_idx = 0
				
			self.question_list_widget.setCurrentRow(self.auto_select_qustion_idx)
			self.auto_select_qustion_idx = -1
	
	def updateQuestionAnswerList(self):
		question, qidx = self.getCurrentQuestion()
		if not question:
			return
		
		answers = question["candidates"]
		for i in range(len(answers)):
			if self.valid_answer_list.count() <= i:
				item = QtWidgets.QListWidgetItem(answers[i])
				item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
				self.valid_answer_list.addItem(item)
			else:
				item = self.valid_answer_list.item(i)
				item.setText(answers[i])
				
			item.setHidden(False)
				
		for i in range(len(answers), self.valid_answer_list.count()):
			item = self.valid_answer_list.item(i)
			item.setHidden(True)
	
	def updateQuestionPartList(self):
		question, qidx = self.getCurrentQuestion()
		if not question:
			return
		
		question_parts = question["parts"]
		for i in range(len(question_parts)):
			if self.part_list_widget.count() <= i:
				item = QtWidgets.QListWidgetItem(str(i + 1))
				item.setSizeHint(QSize(23, 23))
				item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
				self.part_list_widget.addItem(item)
			else:
				item = self.part_list_widget.item(i)
				
			item.setHidden(False)
				
		for i in range(len(question_parts), self.part_list_widget.count()):
			item = self.part_list_widget.item(i)
			item.setHidden(True)
		
	def updateQuestionPartSetting(self):
		question, qidx = self.getCurrentQuestion()
		if not question:
			return
		
		question_part, qidx, idx = self.getCurrentQuestionPart()
		if not question_part:
			return
		
		self.begin_time.setTime(getQTime(question_part[0]))
		self.end_time.setTime(getQTime(question_part[1]))
	
	def updateQuestionDetail(self):
		question, qidx = self.getCurrentQuestion()
		if not question:
			self.media_player.pause()
			self.question_detail_page.setEnabled(False)
			self.current_detail_vid = ""
			return
		
		self.question_detail_page.setEnabled(True)
		
		vid = question["vid"]
		if vid != self.current_detail_vid:
			self.need_reload_media = True
			self.media_player.stop()
			
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
			
		self.current_detail_vid = vid
		
		# 整個右邊頁面刷新時清空答案選擇，避免有隱藏項目被選取
		self.valid_answer_list.clearSelection()
		self.updateQuestionAnswerList()
		
		self.updateQuestionPartList()
		
		if self.auto_select_qustion_part_idx >= 0:
			if self.auto_select_qustion_part_idx >= len(question["parts"]):
				self.auto_select_qustion_part_idx = len(question["parts"]) - 1
				
			self.part_list_widget.setCurrentRow(self.auto_select_qustion_part_idx)
			self.auto_select_qustion_part_idx = -1
		else:
			self.part_list_widget.setCurrentRow(0)
			
		self.updateQuestionPartSetting()
	
	def updatePage(self):
		# 更新整個畫面內容
		self.updateQuestionList()
		self.updateQuestionDetail()
		self.updateWindowTitle()
		
		self.misleading_ans_window.updateMisleadingAnswerList(self.question_set["misleadings"])
		
	# ====================================================================================================
	
	def newFile(self):
		if self.isDirty():
			result = self.check_save.exec()
			if result == QtWidgets.QMessageBox.StandardButton.Yes:
				self.save()
			elif result == QtWidgets.QMessageBox.StandardButton.Cancel:
				return
				
		self.question_set = copy.deepcopy(QUESTION_SET_TEMPLATE)
		self.question_vid_set.clear()
		self.current_detail_vid = ""
		self.file_path = None
		self.resetModifyRecord()
		
		self.updatePage()
	
	def loadFile(self):
		if self.isDirty():
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
		self.resetModifyRecord()
		
		self.question_list_widget.setCurrentRow(0)
		self.updatePage()
	
	def saveReal(self):
		# TODO: 檢查檔案格式，不合理跳警告
		with open(self.file_path, "w") as f:
			f.write(json.dumps(self.question_set))
			
		self.save_modify_record_idx = self.modify_record_idx
		self.updateWindowTitle()
	
	def saveAs(self):
		file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "另存新檔", "", "JSON Files(*.json)")
		if file_path == "":
			return
			
		self.file_path = file_path
		self.saveReal()
	
	def save(self):
		if self.file_path:
			if self.isDirty():
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
		
		# 詢問是否匯入播放清單
		is_playlist = False
		if "&list=" in url:
			result = self.check_all_playlist.exec()
			if result == QtWidgets.QMessageBox.StandardButton.Yes:
				playlist = self.getYoutubePlaylist(url)
				if not playlist:
					self.message_box.critical(self, WINDOW_TITLE, PLAYLIST_ERROR_MSG)
					return
				is_playlist = True
				
		if is_playlist:
			duplicate_count = 0
			invalid_count = 0
			real_add_list = []
			progress = QtWidgets.QProgressDialog("匯入播放清單中...", "取消", 0, len(playlist), self)
			progress.setWindowTitle(WINDOW_TITLE)
			progress.setAutoClose(True)
			progress.setMinimumDuration(500)
			for i, vid in enumerate(playlist):
				if progress.wasCanceled():
					break
					
				progress.setValue(i)
				QtWidgets.QApplication.processEvents()
				
				if vid in self.question_vid_set:
					duplicate_count += 1
					continue
				
				info = self.getYoutubeInfo(vid)
				if not info:
					invalid_count += 1
					continue
				
				question = copy.deepcopy(QUESTION_OBJ_TEMPLATE)
				question["title"] = info["title"]
				question["vid"] = vid
				question["parts"].append([0, 3000])	 # 預設片段是前 3 秒
				question["candidates"].append(info["title"])
				
				real_add_list.append(question)
			
			# 被取消直接放棄所有匯入
			if progress.wasCanceled():
				return
			progress.reset()
			
			for question in real_add_list:
				self.question_set["questions"].append(question)
				self.question_vid_set.add(question["vid"])
				
				self.recordModify(["questions", len(self.question_set["questions"]) - 1], after = question)
			
			self.message_box.information(self, WINDOW_TITLE, f"已匯入播放清單的 {len(playlist)} 部影片\n已忽略重複的 {duplicate_count} 部影片\n共 {invalid_count} 部影片無法載入")
		else:
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
			
			question = copy.deepcopy(QUESTION_OBJ_TEMPLATE)
			question["title"] = info["title"]
			question["vid"] = vid
			question["parts"].append([0, 3000])	 # 預設片段是前 3 秒
			question["candidates"].append(info["title"])
			
			self.question_set["questions"].append(question)
			self.question_vid_set.add(vid)
			
			self.recordModify(["questions", len(self.question_set["questions"]) - 1], after = question)
				
		# 點到新增的那個項目上
		self.updateQuestionList()
		self.question_list_widget.setCurrentRow(len(self.question_set["questions"]) - 1)
		self.updateQuestionDetail()
	
	def delQuestion(self):
		question_list = self.question_set["questions"]
		if len(question_list) == 0:
			return
		
		idx = self.question_list_widget.currentRow()
		if idx >= len(question_list):
			return
		
		self.recordModify(["questions", idx], before = question_list[idx])
		
		self.question_vid_set.remove(question_list[idx]["vid"])
		del question_list[idx]
		
		if idx >= len(question_list):
			self.question_list_widget.setCurrentRow(len(question_list) - 1)
		self.part_list_widget.setCurrentRow(0)
		self.updatePage()
		
	# ====================================================================================================
	
	def addValidAnswer(self):
		question, qidx = self.getCurrentQuestion()
		if not question:
			return
		
		question["candidates"].append(NEW_TEMP_ANSWER)
		self.recordModify(["questions", qidx, "candidates", len(question["candidates"]) - 1], after = NEW_TEMP_ANSWER)
		
		self.updateQuestionAnswerList()
		self.valid_answer_list.scrollToItem(self.valid_answer_list.item(len(question["candidates"]) - 1))
	
	def delValidAnswer(self):
		selected = self.valid_answer_list.selectedItems()
		if len(selected) == 0:
			return
		
		question, qidx = self.getCurrentQuestion()
		if not question:
			return
		
		selected_idx = [self.valid_answer_list.row(item) for item in selected]
		# 要從後面開始刪才不會影響 index
		selected_idx.sort()
		for i in range(len(selected_idx) - 1, -1, -1):
			# 至少要留一個答案
			if selected_idx[i] == 0 and len(question["candidates"]) == 1:
				break
				
			self.recordModify(["questions", qidx, "candidates", selected_idx[i]], before = question["candidates"][selected_idx[i]])
			del question["candidates"][selected_idx[i]]
		
		self.valid_answer_list.clearSelection()
		self.updateQuestionAnswerList()
	
	def editValidAnswer(self, item):
		question, qidx = self.getCurrentQuestion()
		if not question:
			return
		
		# 空字串不接受，顯示回原本內容
		if len(item.text()) == 0:
			self.updateQuestionAnswerList()
			return
		
		idx = self.valid_answer_list.row(item)
		self.recordModify(["questions", qidx, "candidates", idx], before = question["candidates"][idx], after = item.text())
		question["candidates"][idx] = item.text()
		
	# ====================================================================================================
	
	def addMisleadingAnswer(self):
		self.question_set["misleadings"].append(NEW_TEMP_ANSWER)
		self.recordModify(["misleadings", len(self.question_set["misleadings"]) - 1], after = NEW_TEMP_ANSWER)
		
		return self.question_set["misleadings"]
	
	def delMisleadingAnswer(self, selected_idx):
		for i in range(len(selected_idx) - 1, -1, -1):
			if selected_idx[i] < len(self.question_set["misleadings"]):
				self.recordModify(["misleadings", selected_idx[i]], before = self.question_set["misleadings"][selected_idx[i]])
				del self.question_set["misleadings"][selected_idx[i]]
		
		return self.question_set["misleadings"]
	
	def editMisleadingAnswer(self, idx, new_answer):
		self.recordModify(["misleadings", idx], before = self.question_set["misleadings"][idx], after = new_answer)
		self.question_set["misleadings"][idx] = new_answer
	
	# ====================================================================================================
	
	def checkDownloadBeforePlay(self):
		if self.need_reload_media:
			self.need_reload_media = False
			question, qidx = self.getCurrentQuestion()
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
		question_part, qidx, idx = self.getCurrentQuestionPart()
		if not question_part:
			return
			
		# 先下載並載入音檔
		self.checkDownloadBeforePlay()
		
		self.media_player.play()
		self.media_player.setPosition(question_part[0])
		
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
		question, qidx = self.getCurrentQuestion()
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
		question_part, qidx, idx = self.getCurrentQuestionPart()
		if not question_part:
			return
		
		ms = qtime.minute() * 60000 + qtime.second() * 1000 + qtime.msec()
		self.recordModify(["questions", qidx, "parts", idx, 0], before = question_part[0], after = ms)
		question_part[0] = ms

	def setEndTime(self):
		nowTime = getQTime(self.media_player.position())
		self.end_time.setTime(nowTime)

	def endTimeChanged(self, qtime):
		question_part, qidx, idx = self.getCurrentQuestionPart()
		if not question_part:
			return
		
		ms = qtime.minute() * 60000 + qtime.second() * 1000 + qtime.msec()
		self.recordModify(["questions", qidx, "parts", idx, 1], before = question_part[1], after = ms)
		question_part[1] = ms
		
	# ====================================================================================================
	
	def addQuestionPart(self):
		question, qidx = self.getCurrentQuestion()
		if not question:
			return
		
		DEFAULT_PART = [0, 3000]  # 預設片段是前 3 秒
		target_idx = len(question["parts"])
		question["parts"].append(DEFAULT_PART)
		
		self.recordModify(["questions", qidx, "parts", target_idx], after = DEFAULT_PART)
		
		# 點到新增的那個項目上
		self.updateQuestionPartList()
		self.part_list_widget.setCurrentRow(target_idx)
		self.updateQuestionPartSetting()
	
	def delQuestionPart(self):
		question, qidx = self.getCurrentQuestion()
		if not question:
			return
			
		# 至少要留一個片段
		if len(question["parts"]) == 1:
			return
			
		idx = self.part_list_widget.currentRow()
		if idx >= len(question["parts"]):
			return
			
		self.recordModify(["questions", qidx, "parts", idx], before = question["parts"][idx])
		del question["parts"][idx]
		
		self.updateQuestionPartList()
		if idx == len(question["parts"]):  # 刪掉最後一個時一樣幫他選最後一個
			self.part_list_widget.setCurrentRow(idx - 1)
		self.updateQuestionPartSetting()
	
	def movePartLeft(self):
		question, qidx = self.getCurrentQuestion()
		if not question:
			return
			
		idx = self.part_list_widget.currentRow()
		if idx == 0 or idx >= len(question["parts"]):
			return
			
		self.recordModify(["questions", qidx, "parts", [idx, idx - 1]])
		question["parts"][idx], question["parts"][idx - 1] = question["parts"][idx - 1], question["parts"][idx]
		
		self.part_list_widget.setCurrentRow(idx - 1)
	
	def movePartRight(self):
		question, qidx = self.getCurrentQuestion()
		if not question:
			return
			
		idx = self.part_list_widget.currentRow()
		if idx + 1 >= len(question["parts"]):
			return
			
		self.recordModify(["questions", qidx, "parts", [idx, idx + 1]])
		question["parts"][idx], question["parts"][idx + 1] = question["parts"][idx + 1], question["parts"][idx]
		
		self.part_list_widget.setCurrentRow(idx + 1)

if __name__ == '__main__':
	app = QtWidgets.QApplication(sys.argv)
	player = QuestionEditor()
	sys.exit(app.exec())
