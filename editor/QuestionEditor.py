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
		self.mediaPlayer = QMediaPlayer()
		self.audioOutput = QAudioOutput()
		self.mediaPlayer.setAudioOutput(self.audioOutput)

		self.playButton = QPushButton("Play")
		self.playButton.clicked.connect(self.playPause)
		self.frame_audio_player.addWidget(self.playButton)

		self.positionSlider = Slider(Qt.Orientation.Horizontal)
		self.positionSlider.setRange(0, 0)
		self.positionSlider.sliderPressed.connect(self.beginDragPosition)
		self.positionSlider.sliderMoved.connect(self.setPosition)
		self.positionSlider.sliderReleased.connect(self.endDragPosition)
		self.frame_audio_player.addWidget(self.positionSlider)

		self.timeLabel = QLabel("0:00.000 / 0:00.000")
		self.frame_audio_player.addWidget(self.timeLabel)

		self.mediaPlayer.positionChanged.connect(self.positionChanged)
		self.mediaPlayer.durationChanged.connect(self.durationChanged)

		self.setWindowTitle("猜歌機器人題庫編輯器")
		self.show()

	def playPause(self):
		if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
			self.mediaPlayer.pause()
			self.playButton.setText("Play")
		else:
			self.mediaPlayer.setSource(QUrl.fromLocalFile("../temp/1247388511028514928/main.webm"))
			self.mediaPlayer.play()
			self.playButton.setText("Pause")

	def positionChanged(self, position):
		self.positionSlider.setValue(position)
		self.updateTimeLabel()

	def durationChanged(self, duration):
		self.positionSlider.setRange(0, duration)
		self.updateTimeLabel()
	
	def beginDragPosition(self):
		self.dragPositionWasPlaying = self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState
		self.mediaPlayer.pause()

	def setPosition(self, position):
		self.mediaPlayer.setPosition(position)
	
	def endDragPosition(self):
		if self.dragPositionWasPlaying:
			self.mediaPlayer.play()

	def updateTimeLabel(self):
		position = self.mediaPlayer.position()
		duration = self.mediaPlayer.duration()
		position_minutes = position // 60000
		position_seconds = (position // 1000) % 60
		position_ms = position % 1000
		duration_minutes = duration // 60000
		duration_seconds = (duration // 1000) % 60
		duration_ms = duration % 1000
		self.timeLabel.setText(f"{position_minutes}:{position_seconds:02d}.{position_ms:03d} / {duration_minutes}:{duration_seconds:02d}.{duration_ms:03d}")

if __name__ == '__main__':
	app = QApplication(sys.argv)
	player = QuestionEditor()
	sys.exit(app.exec())
