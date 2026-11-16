"""Microphone control and voice telemetry badge widget for JARVIS HUD."""

from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QLabel, QToolTip

from jarvis.config import COLORS
from jarvis.voice.state import VoiceState, VOICE_STATE_META


class VoiceMicWidget(QFrame):
    """
    HUD component displaying microphone status badge, Push-To-Talk trigger,
    and voice cancellation / stop-speaking controls.
    """

    mic_clicked = Signal()
    stop_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VoiceMicWidget")
        self._current_state = VoiceState.IDLE

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Main Mic Toggle Button
        self.mic_btn = QPushButton("🎙 MIC", self)
        self.mic_btn.setObjectName("VoiceMicBtn")
        self.mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_btn.setToolTip("Click to toggle speech recognition or hold [Ctrl+Space] for Push-to-Talk")
        self.mic_btn.clicked.connect(self.mic_clicked.emit)
        layout.addWidget(self.mic_btn)

        # Immediate Stop / Cancel Button (shown during speaking or active listening)
        self.stop_btn = QPushButton("⏹ STOP", self)
        self.stop_btn.setObjectName("VoiceStopBtn")
        self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stop_btn.setToolTip("Immediately stop speech synthesis or cancel listening")
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        self.stop_btn.setVisible(False)
        layout.addWidget(self.stop_btn)

        # Status text badge
        self.badge_label = QLabel("STANDBY", self)
        self.badge_label.setObjectName("VoiceBadgeLabel")
        self.badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.badge_label)

        self.update_state(VoiceState.IDLE)

    def update_state(self, state: VoiceState, meta: Optional[Dict[str, Any]] = None) -> None:
        """Update visual appearance based on VoiceState."""
        self._current_state = state
        if not meta:
            meta = VOICE_STATE_META.get(state, {})

        label_text = meta.get("label", state.value.upper())
        icon = meta.get("icon", "🎙")
        badge_bg = meta.get("badge_color", "#24354E")
        text_fg = meta.get("text_color", "#8BA2C1")

        self.badge_label.setText(label_text)

        # Button styling per state
        if state == VoiceState.LISTENING:
            self.mic_btn.setText(f"{icon} LISTENING")
            self.mic_btn.setStyleSheet(f"""
                QPushButton#VoiceMicBtn {{
                    background-color: #00E5FF;
                    color: #050B14;
                    border: 1px solid #FFFFFF;
                    border-radius: 5px;
                    padding: 9px 16px;
                    font-weight: 900;
                    font-size: 12px;
                }}
            """)
            self.stop_btn.setVisible(True)
            self.stop_btn.setText("⏹ CANCEL")
            self.badge_label.setStyleSheet(f"""
                background-color: #0A2E3D;
                color: #00E5FF;
                border: 1px solid #00E5FF;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: bold;
            """)

        elif state == VoiceState.PROCESSING:
            self.mic_btn.setText(f"{icon} PARSING")
            self.mic_btn.setStyleSheet(f"""
                QPushButton#VoiceMicBtn {{
                    background-color: #FFC107;
                    color: #050B14;
                    border: 1px solid #FFE082;
                    border-radius: 5px;
                    padding: 9px 16px;
                    font-weight: 900;
                    font-size: 12px;
                }}
            """)
            self.stop_btn.setVisible(True)
            self.stop_btn.setText("⏹ CANCEL")
            self.badge_label.setStyleSheet(f"""
                background-color: #2E2606;
                color: #FFC107;
                border: 1px solid #FFC107;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: bold;
            """)

        elif state == VoiceState.SPEAKING:
            self.mic_btn.setText(f"{icon} VOCALIZING")
            self.mic_btn.setStyleSheet(f"""
                QPushButton#VoiceMicBtn {{
                    background-color: #122442;
                    color: #00E5FF;
                    border: 1px solid #00E5FF;
                    border-radius: 5px;
                    padding: 9px 16px;
                    font-weight: bold;
                    font-size: 12px;
                }}
            """)
            self.stop_btn.setVisible(True)
            self.stop_btn.setText("⏹ SILENCE")
            self.badge_label.setStyleSheet(f"""
                background-color: #0C1E36;
                color: #00E5FF;
                border: 1px solid #0078D4;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: bold;
            """)

        elif state == VoiceState.ERROR:
            self.mic_btn.setText(f"{icon} FAULT")
            self.mic_btn.setStyleSheet(f"""
                QPushButton#VoiceMicBtn {{
                    background-color: #380C17;
                    color: #FF3366;
                    border: 1px solid #FF3366;
                    border-radius: 5px;
                    padding: 9px 16px;
                    font-weight: bold;
                    font-size: 12px;
                }}
            """)
            self.stop_btn.setVisible(False)
            self.badge_label.setStyleSheet(f"""
                background-color: #240A10;
                color: #FF3366;
                border: 1px solid #FF3366;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: bold;
            """)

        else:  # IDLE
            self.mic_btn.setText("🎙 MIC")
            self.mic_btn.setStyleSheet(f"""
                QPushButton#VoiceMicBtn {{
                    background-color: {COLORS['bg_panel_elevated']};
                    color: {COLORS['cyan_glow']};
                    border: 1px solid {COLORS['border_subtle']};
                    border-radius: 5px;
                    padding: 9px 16px;
                    font-weight: bold;
                    font-size: 12px;
                }}
                QPushButton#VoiceMicBtn:hover {{
                    border-color: {COLORS['cyan_glow']};
                    background-color: #162646;
                }}
            """)
            self.stop_btn.setVisible(False)
            self.badge_label.setStyleSheet(f"""
                background-color: {COLORS['bg_panel_elevated']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border_subtle']};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: bold;
            """)

        # Style stop button
        self.stop_btn.setStyleSheet(f"""
            QPushButton#VoiceStopBtn {{
                background-color: #380C17;
                color: #FF6B8B;
                border: 1px solid #FF3366;
                border-radius: 5px;
                padding: 9px 12px;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton#VoiceStopBtn:hover {{
                background-color: #5C1224;
                color: #FFFFFF;
            }}
        """)
