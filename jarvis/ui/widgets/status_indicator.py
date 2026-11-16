"""Glowing status badge widget for JARVIS system state."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QBrush, QPen
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from jarvis.config import COLORS


class StatusDot(QWidget):
    """Draws a glowing circular dot indicator."""

    def __init__(self, color_hex: str = COLORS["status_online"], parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 14)
        self.dot_color = QColor(color_hex)

    def set_color(self, color_hex: str):
        self.dot_color = QColor(color_hex)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Outer subtle halo
        halo_color = QColor(self.dot_color)
        halo_color.setAlpha(60)
        painter.setBrush(QBrush(halo_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 14, 14)

        # Inner solid dot
        painter.setBrush(QBrush(self.dot_color))
        painter.drawEllipse(3, 3, 8, 8)


class StatusBadge(QFrame):
    """Encapsulates status dot indicator and status text label."""

    STATES = {
        "ONLINE": (COLORS["status_online"], "SYSTEM ONLINE"),
        "READY": (COLORS["status_online"], "READY"),
        "THINKING": (COLORS["cyan_glow"], "AI THINKING..."),
        "SEARCHING": (COLORS["blue_hover"], "DISCOVERING..."),
        "EXECUTING": (COLORS["status_busy"], "EXECUTING TASK..."),
        "SPEAKING": (COLORS["cyan_glow"], "VOCALIZING..."),
        "NEEDS CONFIRMATION": (COLORS["status_busy"], "CONFIRMATION NEEDED"),
        "BUSY": (COLORS["status_busy"], "SUBSYSTEM BUSY"),
        "SUCCESS": (COLORS["status_success"], "OPERATION SUCCESSFUL"),
        "ERROR": (COLORS["status_error"], "ATTENTION REQUIRED"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("StatusBadge")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        self.dot = StatusDot(COLORS["status_online"], self)
        self.label = QLabel("SYSTEM ONLINE", self)
        self.label.setObjectName("StatusText")
        self.label.setStyleSheet(f"color: {COLORS['cyan_glow']};")

        layout.addWidget(self.dot)
        layout.addWidget(self.label)

    def set_state(self, state_key: str, custom_text: str = None):
        """Update indicator color and label based on predefined state or custom text."""
        state_key = state_key.upper()
        color_hex, default_text = self.STATES.get(state_key, (COLORS["status_online"], state_key))
        text = custom_text or default_text

        self.dot.set_color(color_hex)
        self.label.setText(text)
        self.label.setStyleSheet(f"color: {color_hex};")
