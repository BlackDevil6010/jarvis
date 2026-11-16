"""Now Playing / Voice Interaction card widget matching the top-left card in the UI."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QWidget
)

from jarvis.config import COLORS, LOGO_PATH


class NowPlayingWidget(QFrame):
    """Futuristic translucent glass player card for speech & media controls."""

    mic_toggle_requested = Signal()
    stop_tts_requested = Signal()
    action_requested = Signal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("NowPlayingCard")
        self.is_playing = False
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(f"""
            QFrame#NowPlayingCard {{
                background: rgba(14, 22, 45, 0.75);
                border: 1px solid rgba(0, 240, 255, 0.35);
                border-radius: 16px;
                padding: 10px;
            }}
            QLabel {{
                color: {COLORS['text_primary']};
                font-family: 'Segoe UI', 'Consolas', sans-serif;
            }}
            QPushButton.MediaCtrlBtn {{
                background: rgba(18, 28, 55, 0.8);
                color: {COLORS['cyan_glow']};
                border: 1px solid rgba(0, 240, 255, 0.25);
                border-radius: 14px;
                font-size: 13px;
                font-weight: bold;
                padding: 4px;
            }}
            QPushButton.MediaCtrlBtn:hover {{
                background: rgba(0, 240, 255, 0.25);
                border: 1px solid {COLORS['cyan_glow']};
                color: #ffffff;
            }}
            QPushButton.WindowIconBtn {{
                background: transparent;
                color: {COLORS['text_secondary']};
                border: none;
                font-size: 11px;
                font-family: 'Consolas';
            }}
            QPushButton.WindowIconBtn:hover {{
                color: {COLORS['cyan_glow']};
            }}
            QProgressBar {{
                background: rgba(10, 16, 32, 0.8);
                border: 1px solid rgba(0, 240, 255, 0.2);
                border-radius: 4px;
                height: 5px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLORS['cyan_glow']}, stop:1 #8a2be2);
                border-radius: 3px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # 1. Header with title and decorative window icons
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        card_title = QLabel("Now Playing", self)
        card_title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {COLORS['cyan_glow']}; letter-spacing: 1px;")
        header_layout.addWidget(card_title)
        header_layout.addStretch()

        btn_min = QPushButton("○", self)
        btn_min.setProperty("class", "WindowIconBtn")
        btn_close = QPushButton("✕", self)
        btn_close.setProperty("class", "WindowIconBtn")
        header_layout.addWidget(btn_min)
        header_layout.addWidget(btn_close)
        layout.addLayout(header_layout)

        # 2. Main Content: Thumbnail + Track/Voice Info
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        # Thumbnail with glowing border
        thumb_frame = QFrame(self)
        thumb_frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(10, 16, 32, 0.9);
                border: 1.5px solid {COLORS['cyan_glow']};
                border-radius: 10px;
                padding: 4px;
            }}
        """)
        thumb_layout = QVBoxLayout(thumb_frame)
        thumb_layout.setContentsMargins(0, 0, 0, 0)
        thumb_label = QLabel(thumb_frame)
        if LOGO_PATH.exists():
            px = QPixmap(str(LOGO_PATH))
            if not px.isNull():
                thumb_label.setPixmap(px.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        thumb_label.setFixedSize(56, 56)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_layout.addWidget(thumb_label)
        content_layout.addWidget(thumb_frame)

        # Info lines
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.track_title = QLabel("Neon Drift", self)
        self.track_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {COLORS['cyan_glow']};")

        self.track_artist = QLabel("Digital Serenade • OMEN Voice", self)
        self.track_artist.setStyleSheet(f"font-size: 11px; color: {COLORS['text_secondary']};")

        self.track_status = QLabel("● TTS Engine Ready", self)
        self.track_status.setStyleSheet(f"font-size: 10px; color: {COLORS['status_success']}; font-family: 'Consolas';")

        info_layout.addWidget(self.track_title)
        info_layout.addWidget(self.track_artist)
        info_layout.addWidget(self.track_status)
        content_layout.addLayout(info_layout)
        content_layout.addStretch()

        layout.addLayout(content_layout)

        # 3. Audio Progress Bar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(45)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(5)
        layout.addWidget(self.progress_bar)

        # 4. Controls Row: Shuffle, Prev, Play/Pause, Next, Mic
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setSpacing(8)
        ctrl_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_prev = QPushButton("◀◀", self)
        self.btn_prev.setProperty("class", "MediaCtrlBtn")
        self.btn_prev.setFixedSize(30, 30)
        self.btn_prev.clicked.connect(lambda: self.action_requested.emit("prev"))

        self.btn_play = QPushButton("▶", self)
        self.btn_play.setProperty("class", "MediaCtrlBtn")
        self.btn_play.setFixedSize(34, 34)
        self.btn_play.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLORS['cyan_glow']}, stop:1 #8a2be2);
                color: #050811;
                border: none;
                border-radius: 17px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: #ffffff;
            }}
        """)
        self.btn_play.clicked.connect(self._toggle_play)

        self.btn_next = QPushButton("▶▶", self)
        self.btn_next.setProperty("class", "MediaCtrlBtn")
        self.btn_next.setFixedSize(30, 30)
        self.btn_next.clicked.connect(lambda: self.action_requested.emit("next"))

        self.btn_mic = QPushButton("🎙", self)
        self.btn_mic.setProperty("class", "MediaCtrlBtn")
        self.btn_mic.setFixedSize(30, 30)
        self.btn_mic.clicked.connect(self.mic_toggle_requested.emit)

        self.btn_stop = QPushButton("⏹", self)
        self.btn_stop.setProperty("class", "MediaCtrlBtn")
        self.btn_stop.setFixedSize(30, 30)
        self.btn_stop.clicked.connect(self.stop_tts_requested.emit)

        ctrl_layout.addWidget(self.btn_prev)
        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.btn_next)
        ctrl_layout.addWidget(self.btn_mic)
        ctrl_layout.addWidget(self.btn_stop)

        layout.addLayout(ctrl_layout)

    def _toggle_play(self):
        self.is_playing = not self.is_playing
        self.btn_play.setText("⏸" if self.is_playing else "▶")
        self.track_status.setText("● Streaming Audio" if self.is_playing else "● Audio Paused")

    def set_voice_state(self, state_str: str, text: str = ""):
        self.track_status.setText(f"● Voice: {state_str.upper()}")
        if text:
            self.track_artist.setText(text[:36] + ("..." if len(text) > 36 else ""))
