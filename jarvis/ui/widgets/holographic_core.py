"""Central Segmented Holographic Core Widget inspired by the Arc Reactor / HUD ring."""

import math
from PySide6.QtCore import Qt, QTimer, Signal, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, QRadialGradient, QFont
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QFrame
)

from jarvis.config import COLORS


class HolographicCoreWidget(QWidget):
    """Central segmented tactical HUD circle with search bar and quick action chips."""

    command_submitted = Signal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("HolographicCore")
        self.angle_offset = 0.0
        self.pulse_phase = 0.0
        self.is_animating = True

        self.init_ui()
        self.init_animation()

    def init_ui(self):
        self.setMinimumSize(320, 320)

        # Center content layout positioned within the inner circle
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(10)

        # Title inside core
        self.core_title = QLabel("Directives", self)
        self.core_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.core_title.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['cyan_glow']};
                font-family: 'Segoe UI', 'Consolas', sans-serif;
                font-size: 16px;
                font-weight: 800;
                letter-spacing: 2px;
            }}
        """)
        layout.addWidget(self.core_title)

        # Holographic Search / Input bar
        input_container = QFrame(self)
        input_container.setStyleSheet(f"""
            QFrame {{
                background: rgba(8, 14, 30, 0.9);
                border: 1.5px solid {COLORS['cyan_glow']};
                border-radius: 18px;
                padding: 2px 8px;
            }}
        """)
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(8, 2, 8, 2)
        input_layout.setSpacing(6)

        search_glyph = QLabel("🔍", input_container)
        search_glyph.setStyleSheet(f"color: {COLORS['cyan_glow']}; font-size: 12px; background: transparent; border: none;")
        input_layout.addWidget(search_glyph)

        self.input_field = QLineEdit(input_container)
        self.input_field.setPlaceholderText("Directives or search apps...")
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                color: #ffffff;
                font-family: 'Consolas', 'Segoe UI', monospace;
                font-size: 12px;
                padding: 4px;
            }}
        """)
        self.input_field.returnPressed.connect(self._on_enter_pressed)
        input_layout.addWidget(self.input_field)

        self.btn_exec = QPushButton("⚡", input_container)
        self.btn_exec.setFixedSize(24, 24)
        self.btn_exec.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_exec.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['cyan_glow']};
                color: #050811;
                border-radius: 12px;
                font-weight: bold;
                font-size: 11px;
                border: none;
            }}
            QPushButton:hover {{
                background: #ffffff;
            }}
        """)
        self.btn_exec.clicked.connect(self._on_enter_pressed)
        input_layout.addWidget(self.btn_exec)

        layout.addWidget(input_container)

        # Action chips row
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(6)
        chips_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        chips_data = [
            ("🎵 Music", "open spotify"),
            ("💻 Code", "open code editor"),
            ("🩺 Health", "check system health"),
        ]

        for label, cmd in chips_data:
            btn = QPushButton(label, self)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(14, 24, 52, 0.7);
                    color: {COLORS['text_secondary']};
                    border: 1px solid rgba(0, 240, 255, 0.3);
                    border-radius: 10px;
                    padding: 3px 8px;
                    font-size: 10px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: rgba(0, 240, 255, 0.25);
                    border: 1px solid {COLORS['cyan_glow']};
                    color: {COLORS['cyan_glow']};
                }}
            """)
            btn.clicked.connect(lambda checked, c=cmd: self.command_submitted.emit(c))
            chips_layout.addWidget(btn)

        layout.addLayout(chips_layout)

    def init_animation(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start(33)  # ~30 FPS smooth rotation

    def _on_tick(self):
        self.angle_offset = (self.angle_offset + 0.5) % 360.0
        self.pulse_phase = (self.pulse_phase + 0.05) % (2 * math.pi)
        self.update()

    def _on_enter_pressed(self):
        txt = self.input_field.text().strip()
        if txt:
            self.command_submitted.emit(txt)
            self.input_field.clear()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0
        radius = min(w, h) / 2.0 - 15

        # 1. Ambient Radial Glow behind the core
        glow_grad = QRadialGradient(cx, cy, radius * 1.1)
        pulse_alpha = int(35 + 20 * math.sin(self.pulse_phase))
        glow_grad.setColorAt(0.0, QColor(0, 240, 255, pulse_alpha))
        glow_grad.setColorAt(0.7, QColor(138, 43, 226, int(pulse_alpha * 0.6)))
        glow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx - radius * 1.1, cy - radius * 1.1, radius * 2.2, radius * 2.2))

        # 2. Inner Translucent Glass Circle
        inner_grad = QRadialGradient(cx, cy, radius * 0.85)
        inner_grad.setColorAt(0.0, QColor(14, 24, 50, 220))
        inner_grad.setColorAt(0.9, QColor(8, 14, 30, 240))
        inner_grad.setColorAt(1.0, QColor(0, 240, 255, 60))
        painter.setBrush(QBrush(inner_grad))
        inner_pen = QPen(QColor(0, 240, 255, 100), 1.5)
        painter.setPen(inner_pen)
        painter.drawEllipse(QRectF(cx - radius * 0.82, cy - radius * 0.82, radius * 1.64, radius * 1.64))

        # 3. Segmented Holographic Outer Arcs
        num_segments = 6
        gap_deg = 14
        segment_span = (360.0 / num_segments) - gap_deg

        arc_rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)

        for i in range(num_segments):
            start_angle = self.angle_offset + i * (segment_span + gap_deg)
            # Outer thick neon segment
            outer_pen = QPen(QColor(0, 240, 255, 180), 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(outer_pen)
            painter.drawArc(arc_rect, int(start_angle * 16), int(segment_span * 16))

            # Inner secondary cyan ring segment (reverse rotation)
            inner_rect = QRectF(cx - radius * 0.92, cy - radius * 0.92, radius * 1.84, radius * 1.84)
            inner_start = -self.angle_offset * 1.5 + i * (segment_span + gap_deg)
            inner_pen = QPen(QColor(180, 70, 255, 140), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
            painter.setPen(inner_pen)
            painter.drawArc(inner_rect, int(inner_start * 16), int((segment_span * 0.6) * 16))

        # 4. Tactical Tick Marks on the ring
        tick_pen = QPen(QColor(0, 240, 255, 120), 1.5)
        painter.setPen(tick_pen)
        for i in range(12):
            ang = math.radians(self.angle_offset * 0.3 + i * 30)
            x1 = cx + (radius * 0.84) * math.cos(ang)
            y1 = cy + (radius * 0.84) * math.sin(ang)
            x2 = cx + (radius * 0.89) * math.cos(ang)
            y2 = cy + (radius * 0.89) * math.sin(ang)
            painter.drawLine(x1, y1, x2, y2)

        painter.end()
        super().paintEvent(event)
