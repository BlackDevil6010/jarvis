"""Quick-launch shortcuts bar for desktop utilities."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton


class ShortcutBar(QFrame):
    """Bar displaying one-click execution shortcuts for frequent directives."""

    command_requested = Signal(str)

    SHORTCUTS = [
        ("⚡ Skill Forge", "skills"),
        ("📝 Notepad", "Open Notepad"),
        ("🧮 Calculator", "Open Calculator"),
        ("📁 Explorer", "Open File Explorer"),
        ("📊 System Info", "Show system information"),
        ("🧹 Clear", "clear"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ShortcutBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(10)

        title = QLabel("QUICK DIRECTIVES:", self)
        title.setObjectName("ShortcutHeader")
        layout.addWidget(title)

        for label, cmd in self.SHORTCUTS:
            btn = QPushButton(label, self)
            btn.setProperty("class", "ShortcutBtn")
            btn.clicked.connect(lambda checked=False, command=cmd: self.command_requested.emit(command))
            layout.addWidget(btn)

        layout.addStretch()
