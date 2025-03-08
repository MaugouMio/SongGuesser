import sys, os, json
from PyQt6 import uic
from PyQt6 import QtWidgets, QtGui
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import Qt, QUrl

WINDOW_TITLE = "猜歌機器人題庫編輯器"

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
		
		# 確認是否先存檔的 message box
		self.check_save = QtWidgets.QMessageBox(self)
		self.check_save.setWindowTitle(WINDOW_TITLE)
		self.check_save.setIcon(QtWidgets.QMessageBox.Icon.Information)
		self.check_save.setText("要儲存當前檔案的變更嗎？")
		self.check_save.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No | QtWidgets.QMessageBox.StandardButton.Cancel)
		self.check_save.setDefaultButton(QtWidgets.QMessageBox.StandardButton.Yes)

		self.question_set = dict()
		self.file_path = None
		self.dirty_flag = True
		
		self.dragPositionWasPlaying = False
		
		self.initUI()

	def initUI(self):
		# 選單
		self.action_new.triggered.connect(self.newFile)
		self.action_load.triggered.connect(self.loadFile)
		self.action_save.triggered.connect(self.save)
		self.action_save_as.triggered.connect(self.saveAs)
		
		# 音樂播放器
		self.media_player = QMediaPlayer()
		self.media_player.setSource(QUrl.fromLocalFile("../temp/1247388511028514928/main.webm"))
		self.audioOutput = QAudioOutput()
		self.media_player.setAudioOutput(self.audioOutput)

		self.play_button.clicked.connect(self.playPause)

		self.position_slider = Slider(Qt.Orientation.Horizontal)
		self.position_slider.setRange(0, 0)
		self.position_slider.sliderPressed.connect(self.beginDragPosition)
		self.position_slider.sliderMoved.connect(self.setPosition)
		self.position_slider.sliderReleased.connect(self.endDragPosition)
		self.frame_audio_player.addWidget(self.position_slider)

		self.media_player.positionChanged.connect(self.positionChanged)
		self.media_player.durationChanged.connect(self.durationChanged)

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
		
	# ====================================================================================================
		
	def updateWindowTitle(self):
		if self.file_path:
			save_note = self.dirty_flag and "[*]" or ""
			self.setWindowTitle(f"{WINDOW_TITLE} - {os.path.basename(self.file_path)}" + save_note)
		else:
			self.setWindowTitle(f"{WINDOW_TITLE} - New File")
	
	def updatePage(self):
		# TODO: 更新整個畫面內容
		self.updateWindowTitle()
	
	def newFile(self):
		if self.dirty_flag:
			result = self.check_save.exec()
			if result == QtWidgets.QMessageBox.StandardButton.Yes:
				self.save()
			elif result == QtWidgets.QMessageBox.StandardButton.Cancel:
				return
				
		self.question_set = dict()
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
		self.file_path = file_path
		self.dirty_flag = False
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

	def playPause(self):
		if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
			self.media_player.pause()
			self.play_button.setText("▶")
		else:
			self.media_player.play()
			self.play_button.setText("∎∎")

	def positionChanged(self, position):
		self.position_slider.setValue(position)
		self.updateTimeLabel()

	def durationChanged(self, duration):
		self.position_slider.setRange(0, duration)
		
		duration_minutes = duration // 60000
		duration_seconds = (duration // 1000) % 60
		duration_ms = duration % 1000
		self.duration_label.setText(f"{duration_minutes}:{duration_seconds:02d}.{duration_ms:03d}")
		
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
		position_minutes = position // 60000
		position_seconds = (position // 1000) % 60
		position_ms = position % 1000
		self.position_label.setText(f"{position_minutes}:{position_seconds:02d}.{position_ms:03d}")

if __name__ == '__main__':
	app = QtWidgets.QApplication(sys.argv)
	player = QuestionEditor()
	sys.exit(app.exec())
