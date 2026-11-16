"""Dialog for creating and editing Skill metadata in Skill Forge."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QCheckBox, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt
from jarvis.config import COLORS
from jarvis.skills.models import Skill


class SkillDialog(QDialog):
    """Modal dialog to create or edit a Skill."""

    def __init__(self, parent=None, skill: Skill = None):
        super().__init__(parent)
        self.skill = skill
        self.is_edit = skill is not None

        self.setWindowTitle("Edit Workflow" if self.is_edit else "New Workflow - Skill Forge")
        self.setMinimumWidth(450)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['bg_panel']};
                border: 1px solid {COLORS['border_highlight']};
            }}
            QLabel {{
                color: {COLORS['text_primary']};
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                font-weight: 600;
            }}
            QLineEdit, QTextEdit {{
                background-color: {COLORS['bg_input']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border_subtle']};
                border-radius: 4px;
                padding: 8px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1px solid {COLORS['cyan_glow']};
            }}
            QCheckBox {{
                color: {COLORS['text_secondary']};
                font-size: 12px;
                spacing: 8px;
            }}
            QPushButton#SaveBtn {{
                background-color: {COLORS['blue_accent']};
                color: #ffffff;
                border: 1px solid {COLORS['cyan_glow']};
                border-radius: 4px;
                padding: 8px 18px;
                font-weight: bold;
            }}
            QPushButton#SaveBtn:hover {{
                background-color: {COLORS['blue_hover']};
            }}
            QPushButton#CancelBtn {{
                background-color: transparent;
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border_subtle']};
                border-radius: 4px;
                padding: 8px 18px;
            }}
            QPushButton#CancelBtn:hover {{
                border-color: {COLORS['text_primary']};
                color: {COLORS['text_primary']};
            }}
        """)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Title
        header_text = "EDIT SKILL WORKFLOW" if self.is_edit else "CREATE NEW SKILL WORKFLOW"
        header = QLabel(header_text, self)
        header.setStyleSheet(f"color: {COLORS['cyan_glow']}; font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        # Name field
        layout.addWidget(QLabel("Skill Name *", self))
        self.name_input = QLineEdit(self)
        self.name_input.setPlaceholderText("e.g., Coding Workspace Setup")
        if self.is_edit and self.skill:
            self.name_input.setText(self.skill.name)
        layout.addWidget(self.name_input)

        # Description field
        layout.addWidget(QLabel("Description", self))
        self.desc_input = QTextEdit(self)
        self.desc_input.setPlaceholderText("Brief explanation of what this workflow accomplishes...")
        self.desc_input.setMaximumHeight(80)
        if self.is_edit and self.skill:
            self.desc_input.setPlainText(self.skill.description)
        layout.addWidget(self.desc_input)

        # Enabled toggle
        self.enabled_check = QCheckBox("Enable skill for execution", self)
        self.enabled_check.setChecked(self.skill.enabled if self.is_edit and self.skill else True)
        layout.addWidget(self.enabled_check)

        layout.addSpacing(10)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("CANCEL", self)
        self.cancel_btn.setObjectName("CancelBtn")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("SAVE WORKFLOW", self)
        self.save_btn.setObjectName("SaveBtn")
        self.save_btn.clicked.connect(self.on_save)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

    def on_save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Skill name cannot be empty.")
            return
        if len(name) > 100:
            QMessageBox.warning(self, "Validation Error", "Skill name cannot exceed 100 characters.")
            return

        desc = self.desc_input.toPlainText().strip()
        enabled = self.enabled_check.isChecked()

        if self.is_edit and self.skill:
            self.skill.name = name
            self.skill.description = desc
            self.skill.enabled = enabled
        else:
            self.skill = Skill(name=name, description=desc, enabled=enabled, steps=[])

        self.accept()
