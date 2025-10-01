from config import Global
from PyQt5.QtGui import (QFontDatabase, QIcon, QCursor, QPainter, QColor, QFontDatabase, QRadialGradient, 
                         QBrush, QFontMetrics, QFont, QPen
)
from PyQt5.QtCore import Qt, QPoint, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtWidgets import (QSystemTrayIcon, QMenu, QAction, QOpenGLWidget, QApplication, QLabel, QWidget,
                             QLineEdit, QVBoxLayout
)
import live2d.v3 as live2d
from animator.GUIAnimator import *
from animator.animator import *
from gui.style import style
from utils.other import terminate_thread, capture_screen, check_send_over, sounds_player
from utils.func_queue import FuncQueue
from threading import Thread
import os

class Live2DCanvas(QOpenGLWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ciallo～(∠・ω< )⌒★")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        Global.send_audio_text = None
        self.double_hit = [0, '']

        # 缩放相关属性
        self.scale_factor = 1.0
        self.scale_step = 0.1

        win_width, win_height = Global.character['win_width'], Global.character['win_height']
        self.resize(win_width, win_height)
        screen = QApplication.primaryScreen().geometry()
        self.screen_width, self.screen_height = screen.width(), screen.height()
        x = (self.screen_width - win_width) // 2
        y = (self.screen_height - win_height) // 2
        self.move(x, y)

        self.model: None | live2d.LAppModel = None
        self.dragging = False
        self.drag_position = QPoint()

        # 字体
        Global.font = 'Microsoft YaHei'
        font_db = QFontDatabase()
        font_id = font_db.addApplicationFont("assets\\fonts\\字体.ttf")
        if font_id != -1:
            font_families = font_db.applicationFontFamilies(font_id)
            if font_families:
                Global.font = font_families[0]
        
        style.input_box = style.input_box % (Global.font)
        style.tray_menu = style.tray_menu % (Global.font)
        style.context_menu = style.context_menu % (Global.font)

        # 创建双击特效
        self.click_effect = ClickEffect()

        # 添加输入框
        if Global.input_box:
            self.input_box = QLineEdit(self)
            self.input_box.setPlaceholderText("请输入内容")
            self.input_box.returnPressed.connect(self.on_input_enter)
            self.input_box.setStyleSheet(style.input_box)
            self.input_box.hide()

        # 字幕控件
        self.subtitle_window = SubtitleWindow()
        self.subtitle_window.show()
        self.raise_timer = QTimer()
        self.raise_timer.timeout.connect(self.raise_subtitle)
        self.raise_timer.start(100)

        # 主动对话
        if Global.initiative_wait_range != 'none':
            self.initiative_reset()
            self.initiative_timer = QTimer()
            self.initiative_timer.timeout.connect(self.initiative_check)
            self.initiative_timer.start(1000)
        
        # 气泡
        Global.bubble_widget = BubbleWidget(self)
        
        # 音效
        Global.sounds_player = sounds_player()
        Global.sounds_player.load('click.wav', "assets\sounds\click.wav", 0.5)
        Global.sounds_player.load('exp.wav', "assets\sounds\exp.wav", 0.5)

        self.enter_mouse = False
        self.timer1 = QTimer()
        self.timer1.timeout.connect(self.check_mouse_pos)
        self.timer1.start(100)

        Global.animator1 = SubtitleAnimator1(self.subtitle_window.subtitle_label)
        Global.animator2 = SubtitleAnimator2(self.subtitle_window.subtitle_label)
        Global.func_queue1 = FuncQueue(max_t=2)
        Global.func_queue2 = FuncQueue()

        self.create_tray_icon()

    def raise_subtitle(self):
        self.subtitle_window.raise_()
    
    def initiative_check(self):
        current_time = (time.time() - self.initiative_t) / 60
        if current_time > self.initiative_wait and check_send_over():
            if Global.exist:
                img = capture_screen(Global.required['max_pixels'])
                Global.send_text_thread = Thread(target=Global.send_audio_text, args=(str({'系统': f'用户已经{self.initiative_wait}分钟没与你对话了，请根据当前屏幕内容，找个不重复的、用户感兴趣的话题'}), img), daemon=True)
                Global.send_text_thread.start()
            self.initiative_reset()
    
    def initiative_reset(self):
        if Global.initiative_wait_range != 'none':
            self.initiative_t = time.time()
            self.initiative_wait = random.randint(Global.initiative_wait_range[0], Global.initiative_wait_range[1])
    
    def wheelEvent(self, event):
        if self.model is None:
            return
            
        angle_delta = event.angleDelta().y()
    
        old_scale = self.scale_factor
        if angle_delta < 0:
            self.scale_factor = self.scale_factor + self.scale_step
        else:
            self.scale_factor = self.scale_factor - self.scale_step
        
        if old_scale != self.scale_factor:
            if not self.update_scale():
                self.scale_factor = old_scale
        
        super().wheelEvent(event)

    def update_scale(self):
        new_width = int(Global.character['win_width'] * self.scale_factor)
        new_height = int(Global.character['win_height'] * self.scale_factor)
        
        if new_width < 420:
            return False
        
        current_rect = self.geometry()
        current_x = current_rect.x()
        current_y = current_rect.y()
        
        self.setGeometry(current_x, current_y, new_width, new_height)
        
        self.model.Resize(new_width, new_height)

        self.position_input_box()

        return True
    
    def create_context_menu(self, pos):
        context_menu = QMenu(self)
        context_menu.setAttribute(Qt.WA_TranslucentBackground, True)
        context_menu.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup | Qt.NoDropShadowWindowHint)
        context_menu.setStyleSheet(style.context_menu)

        def sleep():
            Global.sounds_player.play('click.wav')
            Global.exist = not Global.exist
        def clear_history():
            Global.sounds_player.play('click.wav')
            Global.my_agent.messages = Global.my_agent.messages[:1]
        def animate_menu_show(menu):
            self.menu_animation = QPropertyAnimation(menu, b"windowOpacity")
            self.menu_animation.setDuration(200)
            self.menu_animation.setStartValue(0.0)
            self.menu_animation.setEndValue(1.0)
            self.menu_animation.setEasingCurve(QEasingCurve.OutCubic)
            menu.setWindowOpacity(0.0)
            self.menu_animation.start()
        
        if Global.exist:
            sleep_action = QAction("睡眠", self)
            sleep_action.triggered.connect(sleep)
        else:
            sleep_action = QAction("唤醒", self)
            sleep_action.triggered.connect(sleep)
        context_menu.addAction(sleep_action)
        
        context_menu.addSeparator()
        
        clear_action = QAction("清空历史", self)
        clear_action.triggered.connect(clear_history)
        context_menu.addAction(clear_action)
        
        animate_menu_show(context_menu)
        context_menu.exec_(pos)
    
    def create_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon = QIcon("assets\icons\icon.ico")
        self.tray_icon.setIcon(icon)
        
        tray_menu = QMenu()
        tray_menu.setStyleSheet(style.tray_menu)
        tray_menu.setAttribute(Qt.WA_TranslucentBackground, True)
        tray_menu.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup)

        self.penetrate_action = QAction("启用穿透", self)
        self.penetrate_action.setCheckable(True)
        self.penetrate_action.triggered.connect(self.toggle_penetrate)
        tray_menu.addAction(self.penetrate_action)

        tray_menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.setCheckable(True)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.setToolTip("Ciallo～(∠・ω< )⌒★")
        self.tray_icon.show()
    
    def on_input_enter(self):
        text = self.input_box.text().strip()
        
        if text:
            self.input_box.clear()

            Global.animator2.schedule_fade_out()

            if Global.func_queue1.t:
                for t0 in Global.func_queue1.t:
                    terminate_thread(t0)
                Global.func_queue1.__init__()

            if Global.audio_queue.q:
                Global.audio_queue.q = {} 

            if Global.send_text_thread:
                terminate_thread(Global.send_text_thread)
                Global.send_text_thread = None

            if Global.sing_song_thread and Global.rvc.playing:
                terminate_thread(Global.sing_song_thread)
                Global.sing_song_thread = None

            img = None
            if Global.always_screenshot:
                img = capture_screen(Global.required['max_pixels'])
            else:
                if time.time() - Global.screenshot_t < 30:
                    img = capture_screen(Global.required['max_pixels'])
                    Global.screenshot_t = time.time()
                else:
                    for i in Global.shot_word:
                        if i in text:
                            img = capture_screen(Global.required['max_pixels'])
                            Global.screenshot_t = time.time()
                            break

            Global.send_text_thread = Thread(target=Global.send_audio_text, args=(text, img), daemon=True)
            Global.send_text_thread.start()

    def toggle_penetrate(self):
        if self.penetrate_action.isChecked():
            flags = self.windowFlags()
            self.setWindowFlags(flags | Qt.WindowType.WindowTransparentForInput)
            self.penetrate_action.setText("关闭穿透")
            self.show()
        else:
            flags = self.windowFlags()
            self.setWindowFlags(flags & ~Qt.WindowType.WindowTransparentForInput)
            self.penetrate_action.setText("启用穿透")
            self.show()
    
    def quit_app(self):
        self.tray_icon.hide()
        os._exit(0)

    def initializeGL(self):
        live2d.glInit()
        self.model = live2d.LAppModel()
        self.model.LoadModelJson(Global.character["live2d_model"])
        self.model.Resize(self.width(), self.height())
        self.model.SetAutoBlinkEnable(False)
        self.model.SetAutoBreathEnable(True)
        Global.model = self.model

        Global.live2d_animator = Live2dAnimator(self.model)
        Global.blink_animator = BlinkAnimator()
        Global.live2d_animator.add(100, Global.blink_animator)
        Global.eyeball_animator = EyeBallAnimator()
        Global.live2d_animator.add(5, Global.eyeball_animator)
        Global.emotion_animator = EmotionAnimator()
        Global.live2d_animator.add(5, Global.emotion_animator)
        Global.expression_animator = ExpressionAnimator()
        Global.live2d_animator.add(5, Global.expression_animator)
        Global.appearance_animator = AppearanceAnimator(self)
        Global.live2d_animator.add(5, Global.appearance_animator)
        if Global.character["Exp"]["mixanimator_wait_range"] != 'none':
            exp_mix_animator = ExpMixAnimator()
            Global.live2d_animator.add(6, exp_mix_animator)
        if Global.character["Body"]["mixanimator_wait_range"] != 'none':
            body_mix_animator = BodyMixAnimator()
            Global.live2d_animator.add(6, body_mix_animator)
        
        self.position_input_box()
        
        self.startTimer(int(1000 / 60)) # 渲染帧率

    def position_input_box(self):
        if not hasattr(self, 'input_box'):
            return
        
        box_width = 400
        box_height = 50
        
        center_x = (self.width() - box_width) // 2
        center_y = (self.height() - box_height) // 2
        
        win_pos = self.pos()
        
        screen_x = win_pos.x() + center_x
        screen_y = win_pos.y() + center_y
        
        screen = QApplication.primaryScreen().geometry()
        screen_width = screen.width()
        screen_height = screen.height()
        
        if screen_x < 0:
            center_x = -win_pos.x()
        elif screen_x + box_width > screen_width:
            center_x = screen_width - win_pos.x() - box_width
        
        if screen_y < 0:
            center_y = -win_pos.y()
        elif screen_y + box_height > screen_height:
            center_y = screen_height - win_pos.y() - box_height
        
        center_x = max(0, min(center_x, self.width() - box_width))
        center_y = max(0, min(center_y, self.height() - box_height))
        
        self.input_box.setGeometry(center_x, center_y, box_width, box_height)

    def check_mouse_pos(self):
        global_pos = QCursor.pos()

        win_pos = self.pos()
        win_w, win_h = self.width(), self.height()
        x1, x2, y1, y2 = win_pos.x(), win_pos.x()+win_w, win_pos.y(), win_pos.y()+win_h

        if x1 < global_pos.x() < x2 and y1 < global_pos.y() < y2:
            if not self.enter_mouse:
                self.enter_mouse = True

                if hasattr(self, 'input_box') and self.penetrate_action.text() == '启用穿透':
                    self.position_input_box()
                    self.input_box.show()
        else:
            if self.enter_mouse:
                self.enter_mouse = False

                if hasattr(self, 'input_box'):
                    self.input_box.hide()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.dragging:
            self.position_input_box()
            self.move(event.globalPos() - self.drag_position)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if self.model is None:
            return

        if event.button() == Qt.MouseButton.RightButton:
            self.create_context_menu(event.globalPos())
            return
            
        if event.button() == Qt.MouseButton.LeftButton:
            x, y = event.x(), event.y()
            hit_parts = self.model.HitPart(x, y)
            if hit_parts:
                hit_part = Global.parts[hit_parts[0]]
                if hit_part == self.double_hit[1] and time.time() - self.double_hit[0] < 0.4:
                    print('触摸了', hit_part)

                    global_pos = self.mapToGlobal(QPoint(x, y))
                    self.click_effect.start_effect(global_pos.x(), global_pos.y())

                    Global.sounds_player.play('click.wav')
                    Global.bubble_widget.show_bubble(f"触摸了 {hit_part} ♡")

                    Global.animator2.schedule_fade_out()

                    if Global.func_queue1.t:
                        for t0 in Global.func_queue1.t:
                            terminate_thread(t0)
                        Global.func_queue1.__init__()

                    if Global.audio_queue.q:
                        Global.audio_queue.q = {}

                    if Global.send_text_thread:
                        terminate_thread(Global.send_text_thread)
                        Global.send_text_thread = None
                    
                    if Global.sing_song_thread and Global.rvc.playing:
                        terminate_thread(Global.sing_song_thread)
                        Global.sing_song_thread = None

                    Global.send_text_thread = Thread(target=Global.send_audio_text, args=(f'[触摸了你的{hit_part}]',), daemon=True)
                    Global.send_text_thread.start()

                self.double_hit = [time.time(), hit_part]

                self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                self.dragging = True
            else:
                self.dragging = False
                return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
        super().mouseReleaseEvent(event)
        
    def timerEvent(self, _):
        Global.live2d_animator.update()
        self.update()

    def on_draw(self):
        live2d.clearBuffer()
        self.model.Draw()

    def paintGL(self):
        self.model.Update()
        self.on_draw()
    
    def closeEvent(self, event):
        os._exit(0)

class SubtitleWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_window()
        self.setup_subtitle()
        
    def setup_window(self):
        self.setWindowTitle("字幕窗口")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        
    def setup_subtitle(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(100, 0, 100, 100)
        
        # 添加弹性空间，让字幕靠底部显示
        main_layout.addStretch()
        
        self.subtitle_label = QLabel()
        self.subtitle_label.setTextFormat(Qt.TextFormat.RichText)
        self.subtitle_label.setWordWrap(True)
        
        font_id = QFontDatabase.addApplicationFont(r"assets\fonts\字体.ttf")
        if font_id != -1:
            font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
        else:
            font_family = "Arial"
            
        self.subtitle_label.setStyleSheet(f'''
            font-size: 96px; 
            font-family: "{font_family}";
            color: white;
            background-color: transparent;
            padding: 20px;
        ''')
        
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.subtitle_label.setMaximumHeight(400)  # 限制最大高度
        
        main_layout.addWidget(self.subtitle_label)
        self.subtitle_label.setText("")

class ClickEffect(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        
        self._radius = 0
        self._opacity = 1.0
        self.center_x = 0
        self.center_y = 0
        
        self.radius_animation = QPropertyAnimation(self, b"radius")
        self.opacity_animation = QPropertyAnimation(self, b"opacity")
        
        self.radius_animation.finished.connect(self.hide)
        
    @pyqtProperty(float)
    def radius(self):
        return self._radius
    
    @radius.setter
    def radius(self, value):
        self._radius = value
        self.update()
        
    @pyqtProperty(float)
    def opacity(self):
        return self._opacity
    
    @opacity.setter
    def opacity(self, value):
        self._opacity = value
        self.update()
    
    def start_effect(self, x, y):
        self.center_x = x
        self.center_y = y
        self._radius = 0
        self._opacity = 1.0
        
        effect_size = 120
        self.setGeometry(
            x - effect_size // 2, 
            y - effect_size // 2, 
            effect_size, 
            effect_size
        )
        
        self.center_x = effect_size // 2
        self.center_y = effect_size // 2
        
        self.show()
        
        self.radius_animation.setDuration(500)
        self.radius_animation.setStartValue(0)
        self.radius_animation.setEndValue(60)
        self.radius_animation.setEasingCurve(QEasingCurve.OutQuad)
        
        self.opacity_animation.setDuration(500)
        self.opacity_animation.setStartValue(1.0)
        self.opacity_animation.setEndValue(0.0)
        self.opacity_animation.setEasingCurve(QEasingCurve.OutQuad)
        
        self.radius_animation.start()
        self.opacity_animation.start()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        color_rgb = Global.character["ttf_rgb"]
        base_color = QColor(color_rgb[0], color_rgb[1], color_rgb[2])
        
        if self._radius > 0:
            gradient = QRadialGradient(self.center_x, self.center_y, self._radius)

            inner_color = QColor(base_color)
            inner_color.setAlphaF(0.0)
            gradient.setColorAt(0.0, inner_color)
            gradient.setColorAt(0.85, inner_color) 
            
            mid_color = QColor(base_color)
            mid_color.setAlphaF(0.8 * self._opacity)
            gradient.setColorAt(0.7, mid_color)
            
            outer_color = QColor(base_color)
            outer_color.setAlphaF(0.3 * self._opacity)
            gradient.setColorAt(1.0, outer_color)
            
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)
            
            painter.drawEllipse(
                int(self.center_x - self._radius),
                int(self.center_y - self._radius),
                int(self._radius * 2),
                int(self._radius * 2)
            )

class BubbleWidget(QWidget):
    show_bubble_signal = pyqtSignal(str, int)
    hide_bubble_signal = pyqtSignal()
    
    def __init__(self, root):
        super().__init__()
        self.root = root
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        
        self._opacity = 0.0
        self._scale = 0.0
        self.text = ""
        self.padding = 15
        self.border_radius = 20
        self.arrow_size = 12
        
        self.opacity_animation = QPropertyAnimation(self, b"opacity")
        self.scale_animation = QPropertyAnimation(self, b"scale")
        
        self.opacity_animation.finished.connect(self._on_hide_animation_finished)
        self._is_hiding = False
        
        self.font_family = Global.font
        self.font_size = 18
        
        self.auto_hide_timer = QTimer()
        self.auto_hide_timer.timeout.connect(self._hide_bubble_impl)
        
        self.show_bubble_signal.connect(self._show_bubble_impl)
        self.hide_bubble_signal.connect(self._hide_bubble_impl)
    
    @pyqtProperty(float)
    def opacity(self):
        return self._opacity
    
    @opacity.setter
    def opacity(self, value):
        self._opacity = value
        self.update()
        
    @pyqtProperty(float)
    def scale(self):
        return self._scale
    
    @scale.setter
    def scale(self, value):
        self._scale = value
        self.update()
    
    def _on_hide_animation_finished(self):
        """动画结束回调"""
        if self._is_hiding:
            self.hide()
            self._is_hiding = False
    
    def show_bubble(self, text, duration=2000):
        self.show_bubble_signal.emit(text, duration)
    
    def hide_bubble(self):
        self.hide_bubble_signal.emit()
    
    def _show_bubble_impl(self, text, duration):
        self.text = text
        self._opacity = 0.0
        self._scale = 0.0
        self._is_hiding = False
        
        font = self.get_bubble_font()
        font_metrics = QFontMetrics(font)
        
        max_width = 300
        
        text_rect = font_metrics.boundingRect(0, 0, max_width, 0, Qt.AlignCenter | Qt.TextWordWrap, text)
        
        extra_margin = 10
        bubble_width = min(max(text_rect.width() + self.padding * 2 + extra_margin, 100), max_width + self.padding * 2)
        bubble_height = text_rect.height() + self.padding * 2 + self.arrow_size + extra_margin
        
        window_pos = self.root.pos()
        window_size = self.root.size()
        
        bubble_x = window_pos.x() + (window_size.width() - bubble_width) // 2
        bubble_y = window_pos.y() + (window_size.height() - bubble_height) // 2 + int(Global.character["bubble_height"] * self.root.scale_factor)
        
        self.setGeometry(bubble_x, bubble_y, bubble_width, bubble_height)
        
        self.show()
        
        self.opacity_animation.setDuration(300)
        self.opacity_animation.setStartValue(0.0)
        self.opacity_animation.setEndValue(1.0)
        self.opacity_animation.setEasingCurve(QEasingCurve.OutCubic)
        
        self.scale_animation.setDuration(300)
        self.scale_animation.setStartValue(0.0)
        self.scale_animation.setEndValue(1.0)
        self.scale_animation.setEasingCurve(QEasingCurve.OutBack)
        
        self.opacity_animation.start()
        self.scale_animation.start()
        
        if duration > 0:
            self.auto_hide_timer.start(duration)
    
    def _hide_bubble_impl(self):
        self.auto_hide_timer.stop()
        self._is_hiding = True
        
        self.opacity_animation.setDuration(200)
        self.opacity_animation.setStartValue(self._opacity)
        self.opacity_animation.setEndValue(0.0)
        self.opacity_animation.setEasingCurve(QEasingCurve.InCubic)
        
        self.scale_animation.setDuration(200)
        self.scale_animation.setStartValue(self._scale)
        self.scale_animation.setEndValue(0.8)
        self.scale_animation.setEasingCurve(QEasingCurve.InCubic)
        
        self.opacity_animation.start()
        self.scale_animation.start()
    
    def get_bubble_font(self):
        font = QFont(self.font_family, self.font_size)
        font.setBold(True)
        return font
    
    def paintEvent(self, event):
        if self._opacity <= 0:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setOpacity(self._opacity)
        
        center_x = self.width() / 2
        center_y = self.height() / 2
        painter.translate(center_x, center_y)
        painter.scale(self._scale, self._scale)
        painter.translate(-center_x, -center_y)
        
        margin = 3
        bubble_rect = self.rect().adjusted(margin, margin, -margin, -self.arrow_size - margin)
        
        gradient = QRadialGradient(bubble_rect.center(), max(bubble_rect.width(), bubble_rect.height()) / 3)
        
        color_rgb = Global.character["ttf_rgb"]
        accent_color = QColor(color_rgb[0], color_rgb[1], color_rgb[2])
        
        bg_color1 = QColor(0, 0, 0, 200)
        bg_color2 = QColor(0, 0, 0, 160)
        
        gradient.setColorAt(0.0, bg_color1)
        gradient.setColorAt(1.0, bg_color2)
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(accent_color, 2))
        
        painter.drawRoundedRect(bubble_rect, self.border_radius, self.border_radius)
        
        arrow_x = bubble_rect.center().x()
        arrow_y = bubble_rect.bottom()
        
        arrow_points = [
            QPoint(arrow_x - self.arrow_size // 2, arrow_y),
            QPoint(arrow_x + self.arrow_size // 2, arrow_y),
            QPoint(arrow_x, arrow_y + self.arrow_size)
        ]
        
        painter.drawPolygon(arrow_points)
        
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(self.get_bubble_font())
        
        text_padding = self.padding - 2
        text_rect = bubble_rect.adjusted(text_padding, text_padding, -text_padding, -text_padding)
        
        painter.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text)