"""Holographic Header Bar matching the top HUD telemetry in the futuristic interface."""

from datetime import datetime
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QWidget
)

from jarvis.config import APP_NAME, APP_SUBTITLE, COLORS, LOGO_PATH
from jarvis.core.system_info import SystemInfoCollector


class HolographicHeader(QFrame):
    """Futuristic glassmorphism header pill with telemetry and window controls."""

    nav_requested = Signal(int)  # 0: HUD, 1: Skill Forge
    minimize_requested = Signal()
    maximize_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("HolographicHeader")
        self.init_ui()
        self.init_timer()

    def init_ui(self):
        self.setStyleSheet(f"""
            QFrame#HolographicHeader {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(14, 22, 45, 0.85),
                    stop:0.5 rgba(20, 32, 65, 0.75),
                    stop:1 rgba(14, 22, 45, 0.85));
                border: 1px solid rgba(0, 240, 255, 0.4);
                border-radius: 20px;
                margin: 8px 14px 4px 14px;
            }}
            QLabel {{
                color: {COLORS['text_primary']};
                font-family: 'Segoe UI', 'Consolas', sans-serif;
            }}
            QPushButton.HeaderNavBtn {{
                background: rgba(18, 28, 55, 0.7);
                color: {COLORS['text_secondary']};
                border: 1px solid rgba(0, 240, 255, 0.25);
                border-radius: 12px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton.HeaderNavBtn:hover {{
                background: rgba(0, 240, 255, 0.2);
                border: 1px solid {COLORS['cyan_glow']};
                color: #ffffff;
            }}
            QPushButton.HeaderNavBtn:checked {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007acc, stop:1 #8a2be2);
                border: 1px solid {COLORS['cyan_glow']};
                color: #ffffff;
            }}
            QPushButton.WindowControlBtn {{
                background: transparent;
                color: {COLORS['text_secondary']};
                border: none;
                font-family: 'Consolas', monospace;
                font-size: 13px;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 6px;
            }}
            QPushButton.WindowControlBtn:hover {{
                background: rgba(0, 240, 255, 0.2);
                color: {COLORS['cyan_glow']};
            }}
            QPushButton.WindowCloseBtn:hover {{
                background: rgba(255, 56, 96, 0.4);
                color: #ff3860;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(14)

        # 1. Left: Brand Pill
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(8)

        self.logo_label = None
        if LOGO_PATH.exists():
            self.logo_label = QLabel(self)
            px = QPixmap(str(LOGO_PATH))
            if not px.isNull():
                self.logo_label.setPixmap(px.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.logo_label.setFixedSize(28, 28)
                brand_layout.addWidget(self.logo_label)

        brand_text_layout = QVBoxLayout()
        brand_text_layout.setSpacing(0)
        self.brand_title = QLabel(APP_NAME, self)
        self.brand_title.setStyleSheet(f"font-size: 15px; font-weight: 900; color: {COLORS['cyan_glow']}; letter-spacing: 1px;")
        self.brand_subtitle = QLabel("TACTICAL AI HUD", self)
        self.brand_subtitle.setStyleSheet(f"font-size: 9px; font-weight: 700; color: {COLORS['text_secondary']}; letter-spacing: 2px;")
        brand_text_layout.addWidget(self.brand_title)
        brand_text_layout.addWidget(self.brand_subtitle)
        brand_layout.addLayout(brand_text_layout)

        layout.addLayout(brand_layout)
        layout.addStretch()

        # 2. Center: Telemetry Cluster (Network, Clock, CPU, RAM)
        telemetry_layout = QHBoxLayout()
        telemetry_layout.setSpacing(16)

        # Wi-Fi / Online badge
        self.wifi_badge = QLabel("📶 ONLINE", self)
        self.wifi_badge.setStyleSheet(f"color: {COLORS['status_success']}; font-size: 11px; font-weight: bold; font-family: 'Consolas';")
        telemetry_layout.addWidget(self.wifi_badge)

        # CPU & Memory mini readout
        self.metrics_label = QLabel("CPU: --%  |  RAM: --%", self)
        self.metrics_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; font-weight: 600; font-family: 'Consolas';")
        telemetry_layout.addWidget(self.metrics_label)

        # Real-time Clock
        self.clock_label = QLabel("", self)
        self.clock_label.setStyleSheet(f"color: {COLORS['cyan_glow']}; font-size: 12px; font-weight: 800; font-family: 'Consolas';")
        telemetry_layout.addWidget(self.clock_label)

        layout.addLayout(telemetry_layout)
        layout.addStretch()

        # 3. View Switcher Pills
        self.btn_hud = QPushButton("🛰 HUD", self)
        self.btn_hud.setProperty("class", "HeaderNavBtn")
        self.btn_hud.setCheckable(True)
        self.btn_hud.setChecked(True)
        self.btn_hud.clicked.connect(lambda: self._on_nav(0))

        self.btn_skills = QPushButton("⚡ FORGE", self)
        self.btn_skills.setProperty("class", "HeaderNavBtn")
        self.btn_skills.setCheckable(True)
        self.btn_skills.setChecked(False)
        self.btn_skills.clicked.connect(lambda: self._on_nav(1))

        layout.addWidget(self.btn_hud)
        layout.addWidget(self.btn_skills)
        layout.addSpacing(6)

        # 4. Window Controls
        self.min_btn = QPushButton("—", self)
        self.min_btn.setProperty("class", "WindowControlBtn")
        self.min_btn.setFixedSize(26, 26)
        self.min_btn.clicked.connect(self.minimize_requested.emit)

        self.max_btn = QPushButton("□", self)
        self.max_btn.setProperty("class", "WindowControlBtn")
        self.max_btn.setFixedSize(26, 26)
        self.max_btn.clicked.connect(self.maximize_requested.emit)

        self.close_btn = QPushButton("✕", self)
        self.close_btn.setProperty("class", "WindowControlBtn WindowCloseBtn")
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.clicked.connect(self.close_requested.emit)

        layout.addWidget(self.min_btn)
        layout.addWidget(self.max_btn)
        layout.addWidget(self.close_btn)

    def _on_nav(self, idx: int):
        self.btn_hud.setChecked(idx == 0)
        self.btn_skills.setChecked(idx == 1)
        self.nav_requested.emit(idx)

    def set_nav_index(self, idx: int):
        self.btn_hud.setChecked(idx == 0)
        self.btn_skills.setChecked(idx == 1)

    def init_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_telemetry)
        self.timer.start(1000)
        self.update_telemetry()

    def update_telemetry(self):
        now = datetime.now()
        self.clock_label.setText(now.strftime("%H:%M:%S  %d/%m/%Y"))
        try:
            metrics = SystemInfoCollector.get_realtime_metrics()
            cpu = metrics.get("cpu_percent", 0.0)
            ram = metrics.get("memory_percent", 0.0)
            self.metrics_label.setText(f"CPU: {cpu:>4.1f}%  |  RAM: {ram:>4.1f}%")
        except Exception:
            pass
