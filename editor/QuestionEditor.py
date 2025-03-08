import sys
from PyQt6 import uic
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QSlider, QPushButton, QLabel
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import Qt, QUrl

# clickable slider
class Slider(QSlider):
	def mousePressEvent(self, e):
		if e.button() == Qt.MouseButton.LeftButton:
			e.accept()
			x = e.pos().x()
			value = (self.maximum() - self.minimum()) * x // self.width() + self.minimum()
			self.sliderMoved.emit(value)
		return super().mousePressEvent(e)

class QuestionEditor(QMainWindow):
	def __init__(self):
		super().__init__()
		
		uic.loadUi("main.ui", self)

		self.dragPositionWasPlaying = False
		self.initUI()

	def initUI(self):
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

		self.setWindowTitle("猜歌機器人題庫編輯器")
		self.show()

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
	app = QApplication(sys.argv)
	player = QuestionEditor()
	sys.exit(app.exec())
