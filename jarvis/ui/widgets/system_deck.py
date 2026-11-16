"""System Telemetry & App Deck widget matching the bottom-right card in the UI."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QWidget
)

from jarvis.config import COLORS
from jarvis.core.system_info import SystemInfoCollector


class SystemDeckWidget(QFrame):
    """Futuristic card with CPU, RAM, and hardware telemetry gauges."""

    action_requested = Signal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("SystemDeckCard")
        self.init_ui()
        self.init_timer()

    def init_ui(self):
        self.setStyleSheet(f"""
            QFrame#SystemDeckCard {{
                background: rgba(14, 22, 45, 0.75);
                border: 1px solid rgba(0, 240, 255, 0.35);
                border-radius: 16px;
                padding: 10px;
            }}
            QLabel {{
                color: {COLORS['text_primary']};
                font-family: 'Segoe UI', 'Consolas', sans-serif;
            }}
            QProgressBar {{
                background: rgba(10, 16, 32, 0.85);
                border: 1px solid rgba(0, 240, 255, 0.25);
                border-radius: 5px;
                height: 10px;
                text-align: right;
                font-size: 9px;
                color: {COLORS['text_primary']};
            }}
            QProgressBar#CpuBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLORS['cyan_glow']}, stop:1 #007acc);
                border-radius: 4px;
            }}
            QProgressBar#RamBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8a2be2, stop:1 #bf00ff);
                border-radius: 4px;
            }}
            QPushButton.DeckMiniBtn {{
                background: rgba(16, 26, 52, 0.85);
                color: {COLORS['cyan_glow']};
                border: 1px solid rgba(0, 240, 255, 0.25);
                border-radius: 8px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: 600;
            }}
            QPushButton.DeckMiniBtn:hover {{
                background: rgba(0, 240, 255, 0.2);
                border-color: {COLORS['cyan_glow']};
                color: #ffffff;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header
        header = QHBoxLayout()
        title = QLabel("Telemetry Deck", self)
        title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {COLORS['cyan_glow']}; letter-spacing: 1px;")
        header.addWidget(title)
        header.addStretch()

        btn_refresh = QPushButton("⚡ RUN DIAGNOSTICS", self)
        btn_refresh.setProperty("class", "DeckMiniBtn")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.clicked.connect(lambda: self.action_requested.emit("diagnostics"))
        header.addWidget(btn_refresh)
        layout.addLayout(header)

        # CPU gauge
        cpu_header = QHBoxLayout()
        cpu_lbl = QLabel("CPU Utilization", self)
        cpu_lbl.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.cpu_val = QLabel("0.0%", self)
        self.cpu_val.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {COLORS['cyan_glow']}; font-family: 'Consolas';")
        cpu_header.addWidget(cpu_lbl)
        cpu_header.addStretch()
        cpu_header.addWidget(self.cpu_val)
        layout.addLayout(cpu_header)

        self.cpu_bar = QProgressBar(self)
        self.cpu_bar.setObjectName("CpuBar")
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setValue(0)
        self.cpu_bar.setTextVisible(False)
        layout.addWidget(self.cpu_bar)

        # RAM gauge
        ram_header = QHBoxLayout()
        ram_lbl = QLabel("Memory Utilization", self)
        ram_lbl.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.ram_val = QLabel("0.0%", self)
        self.ram_val.setStyleSheet(f"font-size: 11px; font-weight: bold; color: #bf00ff; font-family: 'Consolas';")
        ram_header.addWidget(ram_lbl)
        ram_header.addStretch()
        ram_header.addWidget(self.ram_val)
        layout.addLayout(ram_header)

        self.ram_bar = QProgressBar(self)
        self.ram_bar.setObjectName("RamBar")
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setValue(0)
        self.ram_bar.setTextVisible(False)
        layout.addWidget(self.ram_bar)

        # Quick summary line
        self.summary_lbl = QLabel("Architecture: Windows x64 • All systems nominal", self)
        self.summary_lbl.setStyleSheet(f"font-size: 10px; color: {COLORS['text_muted']}; font-family: 'Consolas';")
        layout.addWidget(self.summary_lbl)

    def init_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_telemetry)
        self.timer.start(1500)
        self.update_telemetry()

    def update_telemetry(self):
        try:
            metrics = SystemInfoCollector.get_realtime_metrics()
            cpu = metrics.get("cpu_percent", 0.0)
            ram = metrics.get("memory_percent", 0.0)
            self.cpu_bar.setValue(int(cpu))
            self.cpu_val.setText(f"{cpu:>4.1f}%")
            self.ram_bar.setValue(int(ram))
            self.ram_val.setText(f"{ram:>4.1f}%")
        except Exception:
            pass
