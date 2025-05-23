import sys, os, json, re, pickle, copy
from collections import OrderedDict

sys.path.insert(0, '..')
from cogs.format_checker import *

import urllib
from urllib.parse import urlparse
from urllib.parse import parse_qs

from yt_dlp import YoutubeDL
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

YOUTUBE_CACHE_INFO_FILE = "cache/data_v2.pickle"
YOUTUBE_CACHE_AUDIO_FILE = "cache/audio_order.pickle"



class UserSetting:
	CACHE_FILE_PATH = "cache/user.json"
	
	@staticmethod
	def Load():
		UserSetting.volume = 50
		UserSetting.cache_size = 100  # MB
		UserSetting.cache_info_count = 300
		UserSetting.load_file_path = ""
		UserSetting.save_new_file_path = ""
		
		if not os.path.isfile(UserSetting.CACHE_FILE_PATH):
			return
		
		with open(UserSetting.CACHE_FILE_PATH, "r", encoding = "utf8") as f:
			userData = json.loads(f.read())
			
			UserSetting.volume = userData.get("volume", 50)
			UserSetting.cache_size = userData.get("cache_size", 100)
			UserSetting.cache_info_count = userData.get("cache_info_count", 300)
			UserSetting.load_file_path = userData.get("load_file_path", "")
			UserSetting.save_new_file_path = userData.get("save_new_file_path", "")
	
	@staticmethod
	def Save():
		with open(UserSetting.CACHE_FILE_PATH, "w", encoding = "utf8") as f:
			f.write(json.dumps({
				"volume": UserSetting.volume,
				"cache_size": UserSetting.cache_size,
				"cache_info_count": UserSetting.cache_info_count,
				"load_file_path": UserSetting.load_file_path,
				"save_new_file_path": UserSetting.save_new_file_path
			}, indent=4))



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



# 參考 settings.ui 生成的程式碼調整
class SettingWindow(QtWidgets.QDialog):
	def __init__(self):
		super().__init__()
		
		self.resize(200, 120)
		self.setMinimumSize(200, 120)
		self.setMaximumSize(200, 120)
		self.setModal(True)
		self.setWindowTitle("設定")
		
		self.verticalLayoutWidget = QtWidgets.QDialog(self)
		self.verticalLayoutWidget.setGeometry(QRect(40, 10, 121, 101))
		self.verticalLayout = QtWidgets.QVBoxLayout(self.verticalLayoutWidget)
		self.verticalLayout.setSpacing(0)
		
		self.label_2 = QtWidgets.QLabel(self.verticalLayoutWidget)
		font = QtGui.QFont()
		font.setBold(True)
		self.label_2.setFont(font)
		self.label_2.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.label_2.setText(QCoreApplication.translate("SettingWindow", u"\u66ab\u5b58\u97f3\u6a94\u5bb9\u91cf\u4e0a\u9650", None))

		self.verticalLayout.addWidget(self.label_2)

		self.cache_size_setter = QtWidgets.QSpinBox(self.verticalLayoutWidget)
		self.cache_size_setter.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.cache_size_setter.setMaximum(100000)
		self.cache_size_setter.setStepType(QtWidgets.QAbstractSpinBox.StepType.AdaptiveDecimalStepType)
		self.cache_size_setter.setValue(UserSetting.cache_size)
		self.cache_size_setter.setSuffix(QCoreApplication.translate("SettingWindow", u" MB", None))
		self.cache_size_setter.valueChanged.connect(self.changeCacheSize)

		self.verticalLayout.addWidget(self.cache_size_setter)

		self.label = QtWidgets.QLabel(self.verticalLayoutWidget)
		self.label.setFont(font)
		self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.label.setText(QCoreApplication.translate("SettingWindow", u"\u66ab\u5b58\u5f71\u7247\u8cc7\u8a0a\u6578\u91cf", None))

		self.verticalLayout.addWidget(self.label)

		self.cache_info_setter = QtWidgets.QSpinBox(self.verticalLayoutWidget)
		self.cache_info_setter.setAlignment(Qt.AlignmentFlag.AlignCenter)
		self.cache_info_setter.setMinimum(1)
		self.cache_info_setter.setMaximum(100000)
		self.cache_info_setter.setStepType(QtWidgets.QAbstractSpinBox.StepType.AdaptiveDecimalStepType)
		self.cache_info_setter.setValue(UserSetting.cache_info_count)
		self.cache_info_setter.valueChanged.connect(self.changeCacheInfo)

		self.verticalLayout.addWidget(self.cache_info_setter)
		self.setLayout(self.verticalLayout)
	
	def changeCacheSize(self, value):
		if value < 0:
			self.cache_size_setter.setValue(UserSetting.cache_size)
		UserSetting.cache_size = value
	
	def changeCacheInfo(self, value):
		if value < 0:
			self.cache_info_setter.setValue(UserSetting.cache_info_count)
		UserSetting.cache_info_count = value

# 參考 misleading_edit.ui 生成的程式碼調整
class MisleadingAnsWindow(QtWidgets.QWidget):
	def __init__(self, addCallback, delCallback, sortCallback, editCallback, undo, redo):
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
		
		self.sort_ans_btn = QtWidgets.QPushButton(self)
		self.sort_ans_btn.setGeometry(QRect(390, 10, 75, 23))
		self.sort_ans_btn.clicked.connect(self.sortMisleadingAnswer)
		self.sort_ans_btn.setText(QCoreApplication.translate("MisleadingAnsWindow", u"\u81ea\u52d5\u6392\u5e8f", None))
		
		self.onAddAnswer = addCallback
		self.onDeleteAnswer = delCallback
		self.onSortAnswer = sortCallback
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
			self.misleading_ans_list.clearSelection()
			self.updateMisleadingAnswerList(answers)
	
	def sortMisleadingAnswer(self):
		if self.onSortAnswer:
			answers = self.onSortAnswer()
			if answers != None:
				self.updateMisleadingAnswerList(answers)
			
	def editMisleadingAnswer(self, item):
		# 空字串不接受，顯示回原本內容
		if len(item.text()) == 0:
			return
			
		newText = item.text()[:MAX_STR_LEN]
		if self.onEditAnswer:
			idx = self.misleading_ans_list.row(item)
			self.onEditAnswer(idx, newText)
		item.setText(newText)

class QuestionEditor(QtWidgets.QMainWindow):
	def __init__(self):
		super().__init__()
		uic.loadUi("main.ui", self)
		
		# 加載使用者設定資料
		UserSetting.Load()
		
		# 影片資訊 cache
		if not os.path.exists("cache"):
			os.mkdir("cache")
		if os.path.isfile(YOUTUBE_CACHE_INFO_FILE):
			with open(YOUTUBE_CACHE_INFO_FILE, "rb") as f:
				self.youtube_cache = pickle.load(f)
				while len(self.youtube_cache) > UserSetting.cache_info_count:
					self.youtube_cache.popitem(last = False)
		else:
			self.youtube_cache = OrderedDict()
			
		# 音檔 cache 紀錄
		if os.path.isfile(YOUTUBE_CACHE_AUDIO_FILE):
			with open(YOUTUBE_CACHE_AUDIO_FILE, "rb") as f:
				self.youtube_audio_cache = pickle.load(f)
		else:
			self.youtube_audio_cache = OrderedDict()
		# 保險起見用現有的檔案刷新一次資訊 (但保留紀錄的順序)
		size_quota = UserSetting.cache_size * 1048576
		self.cache_size_total = 0
		for vid in self.youtube_audio_cache:
			file_path = f"cache/{vid}"
			if os.path.isfile(file_path):
				file_size = os.path.getsize(file_path)
				self.youtube_audio_cache[vid] = file_size
				self.cache_size_total += file_size
			else:
				del self.youtube_audio_cache[vid]
		while self.cache_size_total > size_quota and len(self.youtube_audio_cache) > 0:
			self.cache_size_total -= self.youtube_audio_cache.popitem(last = False)[1]
		# 刪掉沒有控管的檔案
		for file in os.listdir("cache"):
			if "." not in file and file not in self.youtube_audio_cache:
				os.remove(f"cache/{file}")
		
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
		self.next_media_start_time = None
		self.auto_pause_time = -1
		
		self.modify_record = []
		self.modify_record_idx = -1
		self.save_modify_record_idx = -1
		
		self.auto_select_qustion_idx = -1
		self.auto_select_qustion_part_idx = -1
		
		self.search_indexes = []
		self.current_search_index = 0
		
		self.initUI()

	def initUI(self):
		# 選單
		self.action_new.triggered.connect(self.newFile)
		self.action_load.triggered.connect(self.loadFile)
		self.action_save.triggered.connect(self.save)
		self.action_save_as.triggered.connect(self.saveAs)
		self.action_import.triggered.connect(self.importFile)
		
		# 設定視窗
		self.settings_window = SettingWindow()
		self.action_setting.triggered.connect(self.settings_window.show)
		
		# 題庫名稱與作者
		self.question_set_title.editingFinished.connect(self.editTitle)
		self.question_set_author.editingFinished.connect(self.editAuthor)
		
		# 誤導用答案編輯視窗
		self.misleading_ans_window = MisleadingAnsWindow(self.addMisleadingAnswer, self.delMisleadingAnswer, self.sortMisleadingAnswer, self.editMisleadingAnswer, self.undo, self.redo)
		self.edit_misleading_btn.clicked.connect(self.misleading_ans_window.show)
		
		# 題目列表
		self.default_background_brush = QtGui.QBrush()
		self.highlight_background_brush = QtGui.QBrush(QtGui.QColor(255, 255, 0))
		self.highlight_select_background_brush = QtGui.QBrush(QtGui.QColor(255, 127, 0))
		
		self.question_list_widget.itemSelectionChanged.connect(self.updateQuestionDetail)
		self.question_list_widget.itemChanged.connect(self.editQuestionTitle)
		self.add_question_btn.clicked.connect(self.addQuestion)
		self.del_question_btn.clicked.connect(self.delQuestion)
		self.sort_question_btn.clicked.connect(self.sortQuestion)
		
		self.search_input.textEdited.connect(self.updateSearch)
		self.prev_search_btn.clicked.connect(self.prevSearch)
		self.next_search_btn.clicked.connect(self.nextSearch)
		
		# 答案列表
		self.add_ans_btn.clicked.connect(self.addValidAnswer)
		self.del_ans_btn.clicked.connect(self.delValidAnswer)
		self.valid_answer_list.itemChanged.connect(self.editValidAnswer)
		
		# 音樂播放器
		self.media_player = QMediaPlayer()
		self.audio_output = QAudioOutput()
		self.audio_output.setVolume(UserSetting.volume / 100)
		self.media_player.setAudioOutput(self.audio_output)

		self.play_button.clicked.connect(self.playPause)
		self.test_part_button.clicked.connect(self.playPart)
		self.slight_left_button.clicked.connect(self.seekSlightlyLeft)
		self.slight_right_button.clicked.connect(self.seekSlightlyRight)
		self.goto_part_left_btn.clicked.connect(self.gotoPartLeft)
		self.goto_part_right_btn.clicked.connect(self.gotoPartRight)

		self.position_slider = Slider(Qt.Orientation.Horizontal)
		self.position_slider.setRange(0, 0)
		self.position_slider.sliderPressed.connect(self.beginDragPosition)
		self.position_slider.sliderMoved.connect(self.setPosition)
		self.position_slider.sliderReleased.connect(self.endDragPosition)
		self.frame_audio_player.addWidget(self.position_slider)
		
		self.volume_slider.setValue(UserSetting.volume)
		self.volume_slider.valueChanged.connect(self.setVolume)

		self.media_player.positionChanged.connect(self.positionChanged)
		self.media_player.durationChanged.connect(self.durationChanged)
		self.media_player.playbackStateChanged.connect(self.playbackStateChanged)
		self.media_player.mediaStatusChanged.connect(self.mediaStatusChanged)
		
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
			if self.settings_window.isVisible():
				self.settings_window.hide()
			if self.misleading_ans_window.isVisible():
				self.misleading_ans_window.hide()
				
			with open(YOUTUBE_CACHE_INFO_FILE, "wb") as f:
				pickle.dump(self.youtube_cache, f)
			with open(YOUTUBE_CACHE_AUDIO_FILE, "wb") as f:
				pickle.dump(self.youtube_audio_cache, f)
				
			# 儲存使用者偏好資料
			UserSetting.Save()
			
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
		
		if len(record.path) == 1 and record.path[0] == "questions":	 # 排序題目列表 or 匯入題庫
			if len(record.before) != len(record.after):	 # 匯入題庫
				for question in record.after[len(record.before):]:
					self.question_vid_set.remove(question["vid"])
			self.auto_select_qustion_idx = self.getNewSelectQuestionIdx(record.after, record.before)
			
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
			if len(record.path) == 2 and record.path[0] == "questions":	 # undo add question
				self.question_vid_set.remove(target[record.path[-1]]["vid"])
			del target[record.path[-1]]
		elif record.after == None:
			if len(record.path) == 2 and record.path[0] == "questions":	 # undo remove question
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
		
		if len(record.path) == 1 and record.path[0] == "questions":	 # 排序題目列表 or 匯入題庫
			if len(record.before) != len(record.after):	 # 匯入題庫
				for question in record.after[len(record.before):]:
					self.question_vid_set.add(question["vid"])
			self.auto_select_qustion_idx = self.getNewSelectQuestionIdx(record.before, record.after)
		
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
			if len(record.path) == 2 and record.path[0] == "questions":	 # redo remove question
				self.question_vid_set.remove(target[record.path[-1]]["vid"])
			del target[record.path[-1]]
		elif record.before == None:
			if len(record.path) == 2 and record.path[0] == "questions":	 # redo add question
				self.question_vid_set.add(record.after["vid"])
			target.insert(record.path[-1], copy.deepcopy(record.after))
		else:
			target[record.path[-1]] = copy.deepcopy(record.after)
		
		self.updatePage()
		
	# ====================================================================================================

	def getYoutubeInfo(self, vid):
		if vid in self.youtube_cache:
			self.youtube_cache.move_to_end(vid)
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
		while len(self.youtube_cache) > UserSetting.cache_info_count:
			self.youtube_cache.popitem(last = False)
			
		return info
	
	def getYoutubePlaylist(self, url):
		try:
			playlist = Playlist(url)
			return [ link.split("?v=")[1] for link in playlist ]
		except:
			return None

	def downloadYoutube(self, vid):
		if vid in self.youtube_audio_cache:
			self.youtube_audio_cache.move_to_end(vid)
			return
			
		url = f"https://www.youtube.com/watch?v={vid}"
		ytdlp_format_options = {
			'format': 'bestaudio',
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
		with YoutubeDL(ytdlp_format_options) as ytdl:
			ytdl.download(url)
			
		file_size = os.path.getsize(f"cache/{vid}")
		size_quota = UserSetting.cache_size * 1048576
		while self.cache_size_total + file_size > size_quota and len(self.youtube_audio_cache) > 0:
			cache_item = self.youtube_audio_cache.popitem(last = False)
			self.cache_size_total -= cache_item[1]
			os.remove(f"cache/{cache_item[0]}")
			# 順便清掉歌曲長度暫存
			if cache_item[0] in self.youtube_cache:
				del self.youtube_cache[cache_item[0]]["duration"]
		self.youtube_audio_cache[vid] = file_size
		self.cache_size_total += file_size

	def getYoutubeVideoID(self, url):
		youtube_regex = (r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')

		youtube_match = re.match(youtube_regex, url)
		if youtube_match:
			return youtube_match.group(6)
		return ""
	
	def getCurrentQuestion(self):
		question_list = self.question_set["questions"]
		idx = self.question_list_widget.currentRow()
		if idx < 0 or idx >= len(question_list):
			return None, -1
		return question_list[idx], idx
	
	def getCurrentQuestionPart(self):
		question, qidx = self.getCurrentQuestion()
		if not question:
			return None, -1, -1
			
		question_parts = question["parts"]
		idx = self.part_list_widget.currentRow()
		if idx < 0 or idx >= len(question_parts):
			return None, -1, -1
			
		return question_parts[idx], qidx, idx
		
	# ====================================================================================================
		
	def updateWindowTitle(self):
		if self.file_path:
			save_note = self.save_modify_record_idx != self.modify_record_idx and "*" or ""
			self.setWindowTitle(f"{save_note}{os.path.basename(self.file_path)} - {WINDOW_TITLE}")
		else:
			self.setWindowTitle(f"New File - {WINDOW_TITLE}")
		
	def updateQuestionList(self):
		question_list = self.question_set["questions"]
		self.question_list_title.setText(f"題目列表 ({len(question_list)})")
		
		for i in range(len(question_list)):
			if self.question_list_widget.count() <= i:
				item = QtWidgets.QListWidgetItem()
				item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
				self.question_list_widget.addItem(item)
			else:
				item = self.question_list_widget.item(i)
				
			item.setText(question_list[i]["title"])
			item.setHidden(False)
			
			if i in self.search_indexes:
				if i == self.search_indexes[self.current_search_index]:
					item.setBackground(self.highlight_select_background_brush)
				else:
					item.setBackground(self.highlight_background_brush)
			else:
				item.setBackground(self.default_background_brush)
				
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
	
	def updateTitleAuthor(self):
		self.question_set_title.setText(self.question_set["title"])
		self.question_set_author.setText(self.question_set["author"])
	
	def updatePage(self):
		# 更新整個畫面內容
		self.updateTitleAuthor()
		if self.search_input.text() != "":
			self.updateSearch(self.search_input.text(), change_search_select = False)
		else:
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
				
		file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "載入檔案", UserSetting.load_file_path, "JSON Files(*.json)")
		if file_path == "":
			return
		UserSetting.load_file_path = os.path.dirname(file_path)
			
		with open(file_path, "r", encoding="utf8") as f:
			question_set = json.loads(f.read())
			result = validateQuestionFormat(question_set)
			if result not in {FormatErrorCode.OK, FormatErrorCode.EMPTY_QUESTIONS, FormatErrorCode.QUESTION_PART_INVALID_DURATION}:
				self.message_box.critical(self, WINDOW_TITLE, f"題庫檔案格式有誤，錯誤代碼：{result}")
				return
		
		self.question_set = question_set
		self.question_vid_set.clear()
		for question in question_set["questions"]:
			self.question_vid_set.add(question["vid"])
		self.current_detail_vid = ""
		self.file_path = file_path
		self.resetModifyRecord()
		
		self.auto_select_qustion_idx = 0
		self.auto_select_qustion_part_idx = 0
		self.updatePage()
	
	def saveReal(self):
		result = validateQuestionFormat(self.question_set)
		if result != FormatErrorCode.OK:
			if result == FormatErrorCode.EMPTY_QUESTIONS:
				self.message_box.warning(self, WINDOW_TITLE, "題庫中沒有任何題目，將無法使用這份題庫進行遊戲")
			elif result == FormatErrorCode.QUESTION_PART_INVALID_DURATION:
				self.message_box.warning(self, WINDOW_TITLE, "部分音樂片段的長度為0，將無法使用這份題庫進行遊戲")
			else:
				self.message_box.critical(self, WINDOW_TITLE, f"題庫檔案格式有誤，錯誤代碼：{result}")
				return
			
		with open(self.file_path, "w") as f:
			f.write(json.dumps(self.question_set))
			
		self.save_modify_record_idx = self.modify_record_idx
		self.updateWindowTitle()
	
	def saveAs(self):
		file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "另存新檔", UserSetting.save_new_file_path, "JSON Files(*.json)")
		if file_path == "":
			return
		UserSetting.save_new_file_path = os.path.dirname(file_path)
			
		self.file_path = file_path
		self.saveReal()
	
	def save(self):
		if self.file_path:
			if self.isDirty():
				self.saveReal()
		else:
			self.saveAs()
	
	def importFile(self):
		file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "匯入題庫", UserSetting.load_file_path, "JSON Files(*.json)")
		if file_path == "":
			return
		UserSetting.load_file_path = os.path.dirname(file_path)
		
		with open(file_path, "r", encoding="utf8") as f:
			question_set = json.loads(f.read())
			result = validateQuestionFormat(question_set)
			if result != FormatErrorCode.OK:
				self.message_box.critical(self, WINDOW_TITLE, f"題庫檔案格式有誤，錯誤代碼：{result}")
				return
		
		imported = 0
		new_question_list = self.question_set["questions"].copy()
		for question in question_set["questions"]:
			if question["vid"] in self.question_vid_set:
				continue
				
			new_question_list.append(question)
			self.question_vid_set.add(question["vid"])
			imported += 1
			
		if imported > 0:
			self.recordModify(["questions"], before = self.question_set["questions"], after = new_question_list)
			self.question_set["questions"] = new_question_list
			
			if self.search_input.text() != "":
				self.updateSearch(self.search_input.text(), change_search_select = False)
			else:
				self.updateQuestionList()
			
		self.message_box.information(self, WINDOW_TITLE, f"已從 {os.path.basename(file_path)} 匯入 {imported} 個題目")
		
	# ====================================================================================================
	
	def editTitle(self):
		newText = self.question_set_title.text()[:MAX_STR_LEN]
		if len(newText) == 0:
			self.updateTitleAuthor()
			return
			
		self.recordModify(["title"], before = self.question_set["title"], after = newText)
		self.question_set["title"] = newText
		self.updateTitleAuthor()
		
	def editAuthor(self):
		newText = self.question_set_author.text()[:MAX_STR_LEN]
		if len(newText) == 0:
			self.updateTitleAuthor()
			return
			
		self.recordModify(["author"], before = self.question_set["author"], after = newText)
		self.question_set["author"] = newText
		self.updateTitleAuthor()
		
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
				question["title"] = info["title"][:MAX_STR_LEN]
				question["vid"] = vid
				question["parts"].append([0, 3000])	 # 預設片段是前 3 秒
				question["candidates"].append(info["title"][:MAX_STR_LEN])
				
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
			question["title"] = info["title"][:MAX_STR_LEN]
			question["vid"] = vid
			question["parts"].append([0, 3000])	 # 預設片段是前 3 秒
			question["candidates"].append(info["title"][:MAX_STR_LEN])
			
			self.question_set["questions"].append(question)
			self.question_vid_set.add(vid)
			
			self.recordModify(["questions", len(self.question_set["questions"]) - 1], after = question)
				
		if self.search_input.text() != "":
			self.updateSearch(self.search_input.text(), change_search_select = False)
		else:
			self.updateQuestionList()
			
		# 點到新增的那個項目上
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
		
		if self.search_input.text() != "":
			self.updateSearch(self.search_input.text(), change_search_select = False)
		self.updatePage()
	
	def getNewSelectQuestionIdx(self, before_list, after_list):
		# 找到原本選的那個的新 index 選過去
		ori_select_vid = before_list[self.question_list_widget.currentRow()]["vid"]
		for i in range(len(after_list)):
			if after_list[i]["vid"] == ori_select_vid:
				return i
		return 0
	
	def sortQuestion(self):
		question_list = self.question_set["questions"]
		if len(question_list) <= 1:
			return
		
		sorted_list = sorted(question_list, key = lambda q: q["title"])
		if all([question_list[i]["vid"] == sorted_list[i]["vid"] for i in range(len(question_list))]):
			return
		
		self.question_list_widget.setCurrentRow(self.getNewSelectQuestionIdx(question_list, sorted_list))
		
		self.recordModify(["questions"], before=question_list, after=sorted_list)
		self.question_set["questions"] = sorted_list
		self.updatePage()
	
	def editQuestionTitle(self, item):
		# 空字串不接受，顯示回原本內容
		if len(item.text()) == 0:
			self.updateQuestionList()
			return
		
		qidx = self.question_list_widget.row(item)
		if qidx < 0 or qidx >= len(self.question_set["questions"]):
			return
			
		newText = item.text()[:MAX_STR_LEN]
		question = self.question_set["questions"][qidx]
		if question["title"] == newText:
			return
			
		self.recordModify(["questions", qidx, "title"], before = question["title"], after = newText)
		question["title"] = newText
		
		if self.search_input.text() != "":
			self.updateSearch(self.search_input.text(), change_search_select = False)
		else:
			self.updateQuestionList()
		
	def updateSearch(self, text, *, change_search_select = True):
		question_list = self.question_set["questions"]
		current_select = self.question_list_widget.currentRow()
		
		self.search_indexes = []
		if change_search_select:
			self.current_search_index = -1
			
		is_clear_search = text == ""
		if not is_clear_search:
			lower_text = text.lower()
			for i in range(len(question_list)):
				if question_list[i]["title"].lower().find(lower_text) >= 0:
					self.search_indexes.append(i)
					# 自動跳到當前選擇之後的第一個搜尋結果
					if change_search_select and self.current_search_index < 0 and i >= current_select:
						self.current_search_index = len(self.search_indexes) - 1
			
		# 當前選擇之後沒有符合的搜尋就跳回第一個搜尋結果
		if change_search_select and self.current_search_index < 0:
			self.current_search_index = 0
		# 沒有自動重選時，有可能項目變動導致原本選的項目不存在了
		if self.current_search_index >= len(self.search_indexes):
			self.current_search_index = 0
		
		if is_clear_search:
			self.search_count_label.setText("-/-")
			if change_search_select:
				self.question_list_widget.scrollToItem(self.question_list_widget.item(current_select))
		else:
			self.search_count_label.setText(f"{self.current_search_index + 1}/{len(self.search_indexes)}")
			if change_search_select and len(self.search_indexes) > 0:
				self.question_list_widget.scrollToItem(self.question_list_widget.item(self.search_indexes[self.current_search_index]))
			
		self.updateQuestionList()
		
	def prevSearch(self):
		if len(self.search_indexes) > 1:
			self.question_list_widget.item(self.search_indexes[self.current_search_index]).setBackground(self.highlight_background_brush)
			self.current_search_index -= 1
			if self.current_search_index < 0:
				self.current_search_index = len(self.search_indexes) - 1
			self.question_list_widget.item(self.search_indexes[self.current_search_index]).setBackground(self.highlight_select_background_brush)
			
			self.search_count_label.setText(f"{self.current_search_index + 1}/{len(self.search_indexes)}")
		
		if len(self.search_indexes) > 0:
			self.question_list_widget.scrollToItem(self.question_list_widget.item(self.search_indexes[self.current_search_index]))
		
	def nextSearch(self):
		if len(self.search_indexes) > 1:
			self.question_list_widget.item(self.search_indexes[self.current_search_index]).setBackground(self.highlight_background_brush)
			self.current_search_index += 1
			if self.current_search_index >= len(self.search_indexes):
				self.current_search_index = 0
			self.question_list_widget.item(self.search_indexes[self.current_search_index]).setBackground(self.highlight_select_background_brush)
			
			self.search_count_label.setText(f"{self.current_search_index + 1}/{len(self.search_indexes)}")
		
		if len(self.search_indexes) > 0:
			self.question_list_widget.scrollToItem(self.question_list_widget.item(self.search_indexes[self.current_search_index]))
		
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
		
		newText = item.text()[:MAX_STR_LEN]
		idx = self.valid_answer_list.row(item)
		self.recordModify(["questions", qidx, "candidates", idx], before = question["candidates"][idx], after = newText)
		question["candidates"][idx] = newText
		
		self.updateQuestionAnswerList()
		
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
	
	def sortMisleadingAnswer(self):
		ori_list = self.question_set["misleadings"]
		if len(ori_list) <= 1:
			return None
			
		sorted_list = sorted(ori_list)
		if all([ori_list[i] == sorted_list[i] for i in range(len(sorted_list))]):
			return None
		
		self.recordModify(["misleadings"], before=ori_list, after=sorted_list)
		self.question_set["misleadings"] = sorted_list
		
		return self.question_set["misleadings"]
	
	def editMisleadingAnswer(self, idx, new_answer):
		self.recordModify(["misleadings", idx], before = self.question_set["misleadings"][idx], after = new_answer)
		self.question_set["misleadings"][idx] = new_answer
	
	# ====================================================================================================
	
	def checkDownloadBeforePlay(self, start_time = None):
		if self.need_reload_media:
			self.need_reload_media = False
			question, qidx = self.getCurrentQuestion()
			if not question:
				return
			
			vid = question["vid"]
			self.downloadYoutube(vid)
			self.media_player.setSource(QUrl.fromLocalFile(f"cache/{vid}"))
			if start_time != None:
				self.next_media_start_time = start_time
				self.media_player.play()
		else:
			if start_time != None:
				self.media_player.play()
				self.media_player.setPosition(start_time)

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
		self.checkDownloadBeforePlay(question_part[0])
		self.auto_pause_time = question_part[1]
	
	def seekSlightlyLeft(self):
		# 先下載並載入音檔
		self.checkDownloadBeforePlay()
		# 微調時間軸時中斷試聽
		self.auto_pause_time = -1
		
		target_time = max(self.position_slider.value() - 50, 0)
		self.media_player.setPosition(target_time)
		self.media_player.pause()
	
	def seekSlightlyRight(self):
		# 先下載並載入音檔
		self.checkDownloadBeforePlay()
		# 微調時間軸時中斷試聽
		self.auto_pause_time = -1
		
		target_time = min(self.position_slider.value() + 50, self.position_slider.maximum())
		self.media_player.setPosition(target_time)
		self.media_player.pause()
	
	def gotoPartLeft(self):
		question_part, qidx, idx = self.getCurrentQuestionPart()
		if not question_part:
			return
			
		# 先下載並載入音檔
		self.checkDownloadBeforePlay()
		# 跳到指定點時中斷試聽
		self.auto_pause_time = -1
		
		self.media_player.setPosition(question_part[0])
		self.media_player.pause()
	
	def gotoPartRight(self):
		question_part, qidx, idx = self.getCurrentQuestionPart()
		if not question_part:
			return
			
		# 先下載並載入音檔
		self.checkDownloadBeforePlay()
		# 跳到指定點時中斷試聽
		self.auto_pause_time = -1
		
		self.media_player.setPosition(question_part[1])
		self.media_player.pause()
	
	def playbackStateChanged(self, newState):
		if newState == QMediaPlayer.PlaybackState.PlayingState:
			self.play_button.setText("∎∎")
		else:
			self.play_button.setText("▶")
	
	def mediaStatusChanged(self, newState):
		# 加載完自動播放指定位置
		if newState == QMediaPlayer.MediaStatus.BufferedMedia:
			if self.next_media_start_time != None:
				self.media_player.setPosition(self.next_media_start_time)
				self.next_media_start_time = None

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
		UserSetting.volume = volume
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
