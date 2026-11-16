"""Media and Quick Workflow Deck matching the bottom-left card in the UI."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGridLayout, QWidget
)

from jarvis.config import COLORS


class MediaQuickDeck(QFrame):
    """Grid of quick-launch cards with holographic styling."""

    action_requested = Signal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("MediaQuickDeck")
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(f"""
            QFrame#MediaQuickDeck {{
                background: rgba(14, 22, 45, 0.75);
                border: 1px solid rgba(0, 240, 255, 0.35);
                border-radius: 16px;
                padding: 10px;
            }}
            QLabel {{
                color: {COLORS['text_primary']};
                font-family: 'Segoe UI', 'Consolas', sans-serif;
            }}
            QPushButton.DeckTile {{
                background: rgba(16, 26, 52, 0.85);
                color: {COLORS['text_primary']};
                border: 1px solid rgba(0, 240, 255, 0.25);
                border-radius: 10px;
                padding: 8px 6px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
                font-weight: 600;
                text-align: center;
            }}
            QPushButton.DeckTile:hover {{
                background: rgba(0, 240, 255, 0.25);
                border: 1px solid {COLORS['cyan_glow']};
                color: {COLORS['cyan_glow']};
            }}
            QPushButton.DeckTile:pressed {{
                background: rgba(138, 43, 226, 0.4);
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Header
        header = QHBoxLayout()
        title = QLabel("Media & Workflows", self)
        title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {COLORS['cyan_glow']}; letter-spacing: 1px;")
        header.addWidget(title)
        header.addStretch()

        badge = QLabel("READY", self)
        badge.setStyleSheet(f"color: {COLORS['status_success']}; font-size: 9px; font-weight: bold; font-family: 'Consolas';")
        header.addWidget(badge)
        layout.addLayout(header)

        # 2x3 Grid of Tiles
        grid = QGridLayout()
        grid.setSpacing(8)

        tiles = [
            ("🎵 Spotify", "open spotify", 0, 0),
            ("🌐 Browser", "open chrome", 0, 1),
            ("💻 VS Code", "open code editor", 0, 2),
            ("⚡ Skill Forge", "list skills", 1, 0),
            ("🩺 Diagnostics", "show system info", 1, 1),
            ("📁 Documents", "open folder documents", 1, 2),
        ]

        for text, cmd, r, c in tiles:
            btn = QPushButton(text, self)
            btn.setProperty("class", "DeckTile")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, c_name=cmd: self.action_requested.emit(c_name))
            grid.addWidget(btn, r, c)

        layout.addLayout(grid)
