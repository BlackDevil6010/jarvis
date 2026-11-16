"""Dialog for adding or editing an individual action step in Skill Forge."""

from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QCheckBox, QPushButton, QDoubleSpinBox,
    QFileDialog, QStackedWidget, QWidget, QMessageBox
)
from jarvis.config import COLORS
from jarvis.skills.models import SkillStep
from jarvis.skills.action_registry import ActionRegistry


class StepDialog(QDialog):
    """Modal dialog to configure an approved action step within a workflow."""

    def __init__(
        self,
        parent=None,
        registry: Optional[ActionRegistry] = None,
        step: Optional[SkillStep] = None,
        step_order: int = 1
    ):
        super().__init__(parent)
        self.registry = registry or ActionRegistry()
        self.step = step
        self.is_edit = step is not None
        self.step_order = step.order if step else step_order

        self.setWindowTitle("Edit Workflow Step" if self.is_edit else "Add Workflow Step")
        self.setMinimumWidth(500)
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
            QLineEdit, QComboBox, QDoubleSpinBox {{
                background-color: {COLORS['bg_input']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border_subtle']};
                border-radius: 4px;
                padding: 6px 10px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {{
                border: 1px solid {COLORS['cyan_glow']};
            }}
            QCheckBox {{
                color: {COLORS['text_secondary']};
                font-size: 12px;
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
            QPushButton#CancelBtn, QPushButton#BrowseBtn {{
                background-color: transparent;
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border_subtle']};
                border-radius: 4px;
                padding: 6px 14px;
            }}
            QPushButton#CancelBtn:hover, QPushButton#BrowseBtn:hover {{
                border-color: {COLORS['cyan_glow']};
                color: {COLORS['cyan_glow']};
            }}
        """)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        header_text = "EDIT WORKFLOW STEP" if self.is_edit else "ADD WORKFLOW STEP"
        header = QLabel(header_text, self)
        header.setStyleSheet(f"color: {COLORS['cyan_glow']}; font-size: 14px; font-weight: bold;")
        layout.addWidget(header)

        # Step Label / description
        layout.addWidget(QLabel("Step Label (Optional Summary)", self))
        self.label_input = QLineEdit(self)
        self.label_input.setPlaceholderText("e.g., Open Code Workspace")
        if self.step:
            self.label_input.setText(self.step.label)
        layout.addWidget(self.label_input)

        # Action Type Dropdown
        layout.addWidget(QLabel("Approved Action Type *", self))
        self.action_combo = QComboBox(self)

        self.actions = self.registry.get_all_actions()
        for action in self.actions:
            self.action_combo.addItem(f"{action.display_name} ({action.action_type})", action.action_type)

        layout.addWidget(self.action_combo)

        # Stacked Widget for action-specific parameters
        self.param_stack = QStackedWidget(self)
        self.param_widgets = {}

        # 1. launch_app parameters
        w_launch = QWidget()
        l_launch = QVBoxLayout(w_launch)
        l_launch.setContentsMargins(0, 4, 0, 4)
        l_launch.addWidget(QLabel("Application Name or Registered Alias *", w_launch))
        self.app_name_combo = QComboBox(w_launch)
        self.app_name_combo.setEditable(True)
        # Populate with apps from launcher
        registered = self.registry.launcher.db.get_all_applications()
        for a in registered:
            self.app_name_combo.addItem(a["name"])
        l_launch.addWidget(self.app_name_combo)
        self.param_widgets["launch_app"] = w_launch
        self.param_stack.addWidget(w_launch)

        # 2. open_folder parameters
        w_folder = QWidget()
        l_folder = QVBoxLayout(w_folder)
        l_folder.setContentsMargins(0, 4, 0, 4)
        l_folder.addWidget(QLabel("Target Directory Path *", w_folder))
        f_row = QHBoxLayout()
        self.folder_input = QLineEdit(w_folder)
        self.folder_input.setPlaceholderText(r"C:\Projects or %USERPROFILE%\Documents")
        f_browse = QPushButton("BROWSE...", w_folder)
        f_browse.setObjectName("BrowseBtn")
        f_browse.clicked.connect(self.browse_folder)
        f_row.addWidget(self.folder_input, stretch=1)
        f_row.addWidget(f_browse)
        l_folder.addLayout(f_row)
        self.param_widgets["open_folder"] = w_folder
        self.param_stack.addWidget(w_folder)

        # 3. system_diagnostics parameters
        w_diag = QWidget()
        l_diag = QVBoxLayout(w_diag)
        l_diag.setContentsMargins(0, 4, 0, 4)
        diag_desc = QLabel("Captures live CPU utilization, physical/logical core metrics, RAM, disk, and OS uptime.", w_diag)
        diag_desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-style: italic;")
        l_diag.addWidget(diag_desc)
        self.param_widgets["system_diagnostics"] = w_diag
        self.param_stack.addWidget(w_diag)

        # 4. log_message parameters
        w_log = QWidget()
        l_log = QVBoxLayout(w_log)
        l_log.setContentsMargins(0, 4, 0, 4)
        l_log.addWidget(QLabel("Message Content to Output *", w_log))
        self.log_input = QLineEdit(w_log)
        self.log_input.setPlaceholderText("e.g., Development session starting...")
        l_log.addWidget(self.log_input)
        self.param_widgets["log_message"] = w_log
        self.param_stack.addWidget(w_log)

        # 5. delay_step parameters
        w_delay = QWidget()
        l_delay = QVBoxLayout(w_delay)
        l_delay.setContentsMargins(0, 4, 0, 4)
        l_delay.addWidget(QLabel("Delay Duration (Seconds) *", w_delay))
        self.delay_spin = QDoubleSpinBox(w_delay)
        self.delay_spin.setRange(0.1, 60.0)
        self.delay_spin.setValue(1.0)
        self.delay_spin.setSingleStep(0.5)
        l_delay.addWidget(self.delay_spin)
        self.param_widgets["delay_step"] = w_delay
        self.param_stack.addWidget(w_delay)

        layout.addWidget(self.param_stack)

        # Confirmation toggle
        self.confirm_check = QCheckBox("Require explicit user confirmation before running this step (Sensitive action)", self)
        if self.step:
            self.confirm_check.setChecked(self.step.require_confirmation)
        layout.addWidget(self.confirm_check)

        # Connect combo change
        self.action_combo.currentIndexChanged.connect(self.on_action_changed)

        # Prepopulate if editing
        if self.step:
            idx = self.action_combo.findData(self.step.action_type)
            if idx >= 0:
                self.action_combo.setCurrentIndex(idx)
            self.populate_existing_arguments(self.step.action_type, self.step.arguments)
        else:
            self.on_action_changed(0)

        layout.addSpacing(10)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("CANCEL", self)
        self.cancel_btn.setObjectName("CancelBtn")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("SAVE STEP", self)
        self.save_btn.setObjectName("SaveBtn")
        self.save_btn.clicked.connect(self.on_save)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

    def on_action_changed(self, index: int):
        action_type = self.action_combo.currentData()
        widget = self.param_widgets.get(action_type)
        if widget:
            self.param_stack.setCurrentWidget(widget)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder for Workflow Step")
        if folder:
            self.folder_input.setText(folder)

    def populate_existing_arguments(self, action_type: str, args: Dict[str, Any]):
        if action_type == "launch_app":
            app_name = args.get("app_name", "")
            idx = self.app_name_combo.findText(app_name)
            if idx >= 0:
                self.app_name_combo.setCurrentIndex(idx)
            else:
                self.app_name_combo.setEditText(app_name)
        elif action_type == "open_folder":
            self.folder_input.setText(args.get("folder_path", ""))
        elif action_type == "log_message":
            self.log_input.setText(args.get("message", ""))
        elif action_type == "delay_step":
            self.delay_spin.setValue(float(args.get("seconds", 1.0)))

    def on_save(self):
        action_type = self.action_combo.currentData()
        label = self.label_input.text().strip()
        args: Dict[str, Any] = {}

        if action_type == "launch_app":
            app_name = self.app_name_combo.currentText().strip()
            if not app_name:
                QMessageBox.warning(self, "Validation Error", "Please select or type an application name.")
                return
            args["app_name"] = app_name
        elif action_type == "open_folder":
            path = self.folder_input.text().strip()
            if not path:
                QMessageBox.warning(self, "Validation Error", "Please specify a folder path.")
                return
            args["folder_path"] = path
        elif action_type == "log_message":
            msg = self.log_input.text().strip()
            if not msg:
                QMessageBox.warning(self, "Validation Error", "Please enter message text.")
                return
            args["message"] = msg
        elif action_type == "delay_step":
            args["seconds"] = self.delay_spin.value()

        # Validate with Action Registry
        is_valid, err = self.registry.validate_action(action_type, args)
        if not is_valid:
            QMessageBox.warning(self, "Action Validation Error", err or "Validation failed")
            return

        require_conf = self.confirm_check.isChecked()

        if self.is_edit and self.step:
            self.step.action_type = action_type
            self.step.label = label
            self.step.arguments = args
            self.step.require_confirmation = require_conf
        else:
            self.step = SkillStep(
                action_type=action_type,
                order=self.step_order,
                label=label,
                arguments=args,
                require_confirmation=require_conf
            )

        self.accept()
