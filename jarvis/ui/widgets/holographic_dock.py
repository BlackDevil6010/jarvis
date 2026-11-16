"""Bottom Floating Holographic Dock widget matching the floating dock in the UI."""

import math
from PySide6.QtCore import Qt, QTimer, Signal, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, QPainterPath
)
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QPushButton, QWidget
)

from jarvis.config import COLORS


class HolographicDock(QFrame):
    """Floating translucent holographic dock with animated soundwave line."""

    home_clicked = Signal()
    mic_clicked = Signal()
    skills_clicked = Signal()
    music_clicked = Signal()
    apps_clicked = Signal()
    diagnostics_clicked = Signal()
    settings_clicked = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("HolographicDock")
        self.wave_phase = 0.0
        self.is_mic_listening = False
        self.init_ui()
        self.init_animation()

    def init_ui(self):
        self.setFixedHeight(64)
        self.setStyleSheet(f"""
            QFrame#HolographicDock {{
                background: rgba(12, 18, 40, 0.85);
                border: 1.5px solid rgba(0, 240, 255, 0.4);
                border-radius: 24px;
                margin: 0px 40px;
            }}
            QPushButton.DockBtn {{
                background: rgba(18, 28, 58, 0.7);
                color: {COLORS['cyan_glow']};
                border: 1px solid rgba(0, 240, 255, 0.25);
                border-radius: 20px;
                font-size: 16px;
                font-weight: bold;
                padding: 6px;
            }}
            QPushButton.DockBtn:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(0, 240, 255, 0.4), stop:1 rgba(138, 43, 226, 0.4));
                border: 1.5px solid {COLORS['cyan_glow']};
                color: #ffffff;
            }}
            QPushButton#DockMicBtn {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #007acc, stop:1 #8a2be2);
                color: #ffffff;
                border: 1.5px solid {COLORS['cyan_glow']};
                border-radius: 22px;
                font-size: 18px;
            }}
            QPushButton#DockMicBtn:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {COLORS['cyan_glow']}, stop:1 #bf00ff);
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. Home
        self.btn_home = QPushButton("🏠", self)
        self.btn_home.setProperty("class", "DockBtn")
        self.btn_home.setFixedSize(40, 40)
        self.btn_home.setToolTip("Directives HUD (Home)")
        self.btn_home.clicked.connect(self.home_clicked.emit)

        # 2. Music / Media
        self.btn_music = QPushButton("🎵", self)
        self.btn_music.setProperty("class", "DockBtn")
        self.btn_music.setFixedSize(40, 40)
        self.btn_music.setToolTip("Spotify / Media Stream")
        self.btn_music.clicked.connect(self.music_clicked.emit)

        # 3. Central Push-to-Talk Mic
        self.btn_mic = QPushButton("🎙", self)
        self.btn_mic.setObjectName("DockMicBtn")
        self.btn_mic.setFixedSize(44, 44)
        self.btn_mic.setToolTip("Push-to-Talk Voice Interaction (Ctrl+Space)")
        self.btn_mic.clicked.connect(self.mic_clicked.emit)

        # 4. Skill Forge Workflows
        self.btn_skills = QPushButton("⚡", self)
        self.btn_skills.setProperty("class", "DockBtn")
        self.btn_skills.setFixedSize(40, 40)
        self.btn_skills.setToolTip("Skill Forge Multi-Step Workflows")
        self.btn_skills.clicked.connect(self.skills_clicked.emit)

        # 5. Application Discovery
        self.btn_apps = QPushButton("🔍", self)
        self.btn_apps.setProperty("class", "DockBtn")
        self.btn_apps.setFixedSize(40, 40)
        self.btn_apps.setToolTip("Windows Application Discovery")
        self.btn_apps.clicked.connect(self.apps_clicked.emit)

        # 6. Diagnostics Telemetry
        self.btn_diag = QPushButton("📊", self)
        self.btn_diag.setProperty("class", "DockBtn")
        self.btn_diag.setFixedSize(40, 40)
        self.btn_diag.setToolTip("System Telemetry Diagnostics")
        self.btn_diag.clicked.connect(self.diagnostics_clicked.emit)

        # 7. Settings / Keys
        self.btn_settings = QPushButton("⚙", self)
        self.btn_settings.setProperty("class", "DockBtn")
        self.btn_settings.setFixedSize(40, 40)
        self.btn_settings.setToolTip("AI Provider & Credentials")
        self.btn_settings.clicked.connect(self.settings_clicked.emit)

        layout.addWidget(self.btn_home)
        layout.addWidget(self.btn_music)
        layout.addWidget(self.btn_mic)
        layout.addWidget(self.btn_skills)
        layout.addWidget(self.btn_apps)
        layout.addWidget(self.btn_diag)
        layout.addWidget(self.btn_settings)

    def init_animation(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_wave_tick)
        self.timer.start(40)  # 25 FPS wave

    def _on_wave_tick(self):
        self.wave_phase = (self.wave_phase + 0.08) % (2 * math.pi)
        self.update()

    def set_listening_state(self, is_listening: bool):
        self.is_mic_listening = is_listening
        if is_listening:
            self.btn_mic.setStyleSheet(f"""
                QPushButton#DockMicBtn {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {COLORS['cyan_glow']}, stop:1 #ff007f);
                    border: 2px solid #ffffff;
                }}
            """)
        else:
            self.btn_mic.setStyleSheet("")

    def paintEvent(self, event):
        super().paintEvent(event)
        # Draw flowing holographic audio sine wave through the dock
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        mid_y = h / 2.0 + 10

        wave_path = QPainterPath()
        wave_path.moveTo(40, mid_y)

        amp = 8.0 if self.is_mic_listening else 4.0
        step = 6
        for x in range(40, w - 40, step):
            y = mid_y + amp * math.sin((x * 0.03) + self.wave_phase)
            wave_path.lineTo(x, y)

        wave_pen = QPen(QColor(0, 240, 255, 70), 1.5)
        painter.setPen(wave_pen)
        painter.drawPath(wave_path)

        # Secondary violet wave
        wave2_path = QPainterPath()
        wave2_path.moveTo(40, mid_y)
        for x in range(40, w - 40, step):
            y = mid_y + (amp * 0.7) * math.sin((x * 0.04) - self.wave_phase)
            wave2_path.lineTo(x, y)

        wave2_pen = QPen(QColor(180, 70, 255, 60), 1.2)
        painter.setPen(wave2_pen)
        painter.drawPath(wave2_path)

        painter.end()
