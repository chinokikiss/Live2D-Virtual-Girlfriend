import time
from config import Global
from PyQt5.QtWidgets import QGraphicsOpacityEffect
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QPropertyAnimation

class SubtitleAnimator1(QObject):
    update_subtitle = pyqtSignal(str)
    
    def __init__(self, subtitle_label):
        super().__init__()
        self.subtitle_label = subtitle_label
        self.update_subtitle.connect(self.subtitle_label.setText)
    
    def animate_subtitle(self, text, add):
        sleep_time = 0.1 / len(add)
        color = Global.character["ttf_rgb"]
        base_text = "".join([f'<span style="color: rgba({color[0]}, {color[1]}, {color[2]}, 1);">{char}</span>' for char in text])
        
        for char in add:
            for i in range(5):
                alpha = (i + 1) * 255 / 5
                current_text = base_text + f'<span style="color: rgba({color[0]}, {color[1]}, {color[2]}, {alpha/255:.2f});">{char}</span>'

                self.update_subtitle.emit(current_text)
                time.sleep(sleep_time / 5)
            base_text += f'<span style="color: rgba({color[0]}, {color[1]}, {color[2]}, 1);">{char}</span>'

class SubtitleAnimator2(QObject):
    update_subtitle = pyqtSignal(str)
    schedule_fade_signal = pyqtSignal()
    cancel_fade_signal = pyqtSignal()

    def __init__(self, subtitle_label):
        super().__init__()
        self.subtitle_label = subtitle_label
        self.fade_timer = None

        self.opacity_effect = QGraphicsOpacityEffect(self.subtitle_label)
        self.subtitle_label.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(1.0)

        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(1000)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)

        self.update_subtitle.connect(self._set_text_and_reset_opacity)
        self.schedule_fade_signal.connect(self._schedule_fade_out)
        self.cancel_fade_signal.connect(self._cancel_fade_out)
        self.fade_animation.finished.connect(self._reset_subtitle_state)

    def _set_text_and_reset_opacity(self, text):
        self._cancel_fade_out()
        self.subtitle_label.setText(text)
        self.opacity_effect.setOpacity(1.0)

    def _schedule_fade_out(self):
        self._cancel_fade_out()

        self.fade_timer = QTimer()
        self.fade_timer.setSingleShot(True)
        self.fade_timer.timeout.connect(self._start_fade_animation)
        self.fade_timer.start(2000)

    def _start_fade_animation(self):
        self.fade_animation.start()

    def _cancel_fade_out(self):
        if self.fade_timer and self.fade_timer.isActive():
            self.fade_timer.stop()
            self.fade_timer = None

        if self.fade_animation and self.fade_animation.state() == QPropertyAnimation.Running:
            self.fade_animation.stop()

        self.opacity_effect.setOpacity(1.0)

    def _reset_subtitle_state(self):
        self.subtitle_label.setText("")
        self.opacity_effect.setOpacity(1.0)

    def schedule_fade_out(self):
        self.schedule_fade_signal.emit()

    def cancel_fade_out(self):
        self.cancel_fade_signal.emit()