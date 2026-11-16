"""Primary Skill Forge view for managing, configuring, testing, and running workflows."""

import json
from typing import Optional
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QTextEdit, QProgressBar,
    QFrame, QMessageBox, QSplitter
)

from jarvis.config import COLORS
from jarvis.skills.models import (
    Skill, SkillStep, SkillExecutionResult, StepStatus, WorkflowStatus
)
from jarvis.skills.storage import SkillStorage
from jarvis.skills.action_registry import ActionRegistry
from jarvis.skills.engine import SkillExecutionEngine, CancellationToken
from jarvis.ui.skills.skill_dialog import SkillDialog
from jarvis.ui.skills.step_dialog import StepDialog


class SkillWorker(QThread):
    """Executes a workflow asynchronously to keep GUI interactive."""

    step_progress_signal = Signal(str, str, str)  # step_id, status, message
    workflow_finished_signal = Signal(object)      # SkillExecutionResult
    request_confirmation_signal = Signal(str, str) # step_id, prompt_text

    def __init__(
        self,
        engine: SkillExecutionEngine,
        skill: Skill,
        dry_run: bool = False
    ):
        super().__init__()
        self.engine = engine
        self.skill = skill
        self.dry_run = dry_run
        self.token = CancellationToken()
        self.confirmation_response: Optional[bool] = None

    def cancel(self):
        self.token.cancel()

    def run(self):
        def on_step_progress(step: SkillStep, status: str, msg: str):
            self.step_progress_signal.emit(step.id, status, msg)

        def on_confirmation(step: SkillStep) -> bool:
            # Emit signal to main thread and wait
            prompt = f"Action: {step.action_type.upper()}\nLabel: {step.label or 'Unlabeled'}\nArguments: {json.dumps(step.arguments)}"
            self.confirmation_response = None
            self.request_confirmation_signal.emit(step.id, prompt)

            # Wait for main thread response
            while self.confirmation_response is None:
                if self.token.is_cancelled:
                    return False
                self.msleep(50)
            return self.confirmation_response

        result = self.engine.execute_skill(
            self.skill,
            dry_run=self.dry_run,
            cancellation_token=self.token,
            step_progress_callback=on_step_progress,
            confirmation_callback=on_confirmation
        )
        self.workflow_finished_signal.emit(result)


class SkillForgeView(QWidget):
    """Futuristic Cyber HUD interface for Skill Forge."""

    def __init__(self, parent=None, storage: Optional[SkillStorage] = None, registry: Optional[ActionRegistry] = None):
        super().__init__(parent)
        self.storage = storage or SkillStorage()
        self.registry = registry or ActionRegistry()
        self.engine = SkillExecutionEngine(registry=self.registry, storage=self.storage)

        self.current_skill: Optional[Skill] = None
        self.worker: Optional[SkillWorker] = None

        self.init_ui()
        self.reload_skills_list()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header
        header_frame = QFrame(self)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_box = QVBoxLayout()
        title = QLabel("SKILL FORGE // WORKFLOW WORKSHOP", self)
        title.setStyleSheet(f"color: {COLORS['cyan_glow']}; font-size: 20px; font-weight: bold;")
        subtitle = QLabel("Create, validate, test, and run automated multi-step desktop workflows", self)
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        main_layout.addWidget(header_frame)

        # Splitter Layout (Left: Skill List, Right: Skill Editor/Runner)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {COLORS['border_subtle']};
                width: 2px;
            }}
        """)

        # LEFT PANEL: Skill List
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(8)

        search_label = QLabel("REGISTERED SKILLS", left_widget)
        search_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold; font-size: 11px;")
        left_layout.addWidget(search_label)

        self.search_input = QLineEdit(left_widget)
        self.search_input.setPlaceholderText("Filter skills...")
        self.search_input.textChanged.connect(self.filter_skills)
        self.search_input.setStyleSheet(f"""
            background-color: {COLORS['bg_input']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border_subtle']};
            border-radius: 4px;
            padding: 6px;
        """)
        left_layout.addWidget(self.search_input)

        self.skill_list = QListWidget(left_widget)
        self.skill_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {COLORS['bg_panel']};
                border: 1px solid {COLORS['border_subtle']};
                border-radius: 6px;
                color: {COLORS['text_primary']};
            }}
            QListWidget::item {{
                padding: 10px;
                border-bottom: 1px solid {COLORS['border_subtle']};
            }}
            QListWidget::item:selected {{
                background-color: #122442;
                border-left: 3px solid {COLORS['cyan_glow']};
                color: {COLORS['cyan_glow']};
            }}
            QListWidget::item:hover {{
                background-color: #0c182d;
            }}
        """)
        self.skill_list.currentItemChanged.connect(self.on_skill_selected)
        left_layout.addWidget(self.skill_list)

        # Buttons under list
        list_btn_layout = QHBoxLayout()
        self.btn_new_skill = QPushButton("+ NEW SKILL", left_widget)
        self.btn_new_skill.clicked.connect(self.on_create_skill)
        self.style_button(self.btn_new_skill, primary=True)

        self.btn_dup_skill = QPushButton("DUPLICATE", left_widget)
        self.btn_dup_skill.clicked.connect(self.on_duplicate_skill)
        self.style_button(self.btn_dup_skill)

        self.btn_del_skill = QPushButton("DELETE", left_widget)
        self.btn_del_skill.clicked.connect(self.on_delete_skill)
        self.style_button(self.btn_del_skill, danger=True)

        list_btn_layout.addWidget(self.btn_new_skill)
        list_btn_layout.addWidget(self.btn_dup_skill)
        list_btn_layout.addWidget(self.btn_del_skill)
        left_layout.addLayout(list_btn_layout)

        self.btn_toggle_enable = QPushButton("TOGGLE ENABLED / DISABLED", left_widget)
        self.btn_toggle_enable.clicked.connect(self.on_toggle_enable)
        self.style_button(self.btn_toggle_enable)
        left_layout.addWidget(self.btn_toggle_enable)

        splitter.addWidget(left_widget)

        # RIGHT PANEL: Skill Detail, Step Editor, Execution
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(10)

        # Top Skill Details Card
        self.skill_header_frame = QFrame(right_widget)
        self.skill_header_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['bg_panel']};
                border: 1px solid {COLORS['border_subtle']};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        header_inner = QHBoxLayout(self.skill_header_frame)

        info_box = QVBoxLayout()
        self.skill_title_label = QLabel("Select a skill to view details", self.skill_header_frame)
        self.skill_title_label.setStyleSheet(f"color: {COLORS['cyan_glow']}; font-size: 16px; font-weight: bold;")
        self.skill_desc_label = QLabel("", self.skill_header_frame)
        self.skill_desc_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        info_box.addWidget(self.skill_title_label)
        info_box.addWidget(self.skill_desc_label)
        header_inner.addLayout(info_box, stretch=1)

        self.skill_status_badge = QLabel("ENABLED", self.skill_header_frame)
        self.skill_status_badge.setStyleSheet(f"color: {COLORS['status_success']}; font-weight: bold; border: 1px solid {COLORS['status_success']}; border-radius: 4px; padding: 4px 8px;")
        header_inner.addWidget(self.skill_status_badge)

        self.btn_edit_meta = QPushButton("EDIT INFO", self.skill_header_frame)
        self.btn_edit_meta.clicked.connect(self.on_edit_skill_meta)
        self.style_button(self.btn_edit_meta)
        header_inner.addWidget(self.btn_edit_meta)

        right_layout.addWidget(self.skill_header_frame)

        # Steps Table
        steps_header_layout = QHBoxLayout()
        steps_lbl = QLabel("WORKFLOW SEQUENCE STEPS", right_widget)
        steps_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; font-weight: bold; font-size: 11px;")
        steps_header_layout.addWidget(steps_lbl)
        steps_header_layout.addStretch()

        self.btn_add_step = QPushButton("+ ADD STEP", right_widget)
        self.btn_add_step.clicked.connect(self.on_add_step)
        self.style_button(self.btn_add_step, primary=True)
        steps_header_layout.addWidget(self.btn_add_step)
        right_layout.addLayout(steps_header_layout)

        self.steps_table = QTableWidget(right_widget)
        self.steps_table.setColumnCount(5)
        self.steps_table.setHorizontalHeaderLabels(["#", "Action Type", "Label", "Arguments", "Confirmation"])
        self.steps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.steps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.steps_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.steps_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.steps_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.steps_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['bg_panel']};
                border: 1px solid {COLORS['border_subtle']};
                border-radius: 6px;
                color: {COLORS['text_primary']};
                gridline-color: {COLORS['border_subtle']};
            }}
            QHeaderView::section {{
                background-color: #0d1526;
                color: {COLORS['text_secondary']};
                padding: 6px;
                border: 1px solid {COLORS['border_subtle']};
                font-weight: bold;
                font-size: 11px;
            }}
            QTableWidget::item:selected {{
                background-color: #122442;
                color: {COLORS['cyan_glow']};
            }}
        """)
        self.steps_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        right_layout.addWidget(self.steps_table, stretch=1)

        # Step reordering and management buttons
        step_ctrl_layout = QHBoxLayout()
        self.btn_move_up = QPushButton("▲ MOVE UP", right_widget)
        self.btn_move_up.clicked.connect(self.on_move_step_up)
        self.style_button(self.btn_move_up)

        self.btn_move_down = QPushButton("▼ MOVE DOWN", right_widget)
        self.btn_move_down.clicked.connect(self.on_move_step_down)
        self.style_button(self.btn_move_down)

        self.btn_edit_step = QPushButton("✏ EDIT STEP", right_widget)
        self.btn_edit_step.clicked.connect(self.on_edit_step)
        self.style_button(self.btn_edit_step)

        self.btn_delete_step = QPushButton("🗑 REMOVE STEP", right_widget)
        self.btn_delete_step.clicked.connect(self.on_delete_step)
        self.style_button(self.btn_delete_step, danger=True)

        step_ctrl_layout.addWidget(self.btn_move_up)
        step_ctrl_layout.addWidget(self.btn_move_down)
        step_ctrl_layout.addWidget(self.btn_edit_step)
        step_ctrl_layout.addWidget(self.btn_delete_step)
        step_ctrl_layout.addStretch()
        right_layout.addLayout(step_ctrl_layout)

        # Execution Controls
        exec_ctrl_layout = QHBoxLayout()
        self.btn_run_skill = QPushButton("▶ RUN WORKFLOW", right_widget)
        self.btn_run_skill.clicked.connect(lambda: self.start_execution(dry_run=False))
        self.style_button(self.btn_run_skill, primary=True)

        self.btn_dry_run = QPushButton("🔍 DRY RUN (TEST)", right_widget)
        self.btn_dry_run.clicked.connect(lambda: self.start_execution(dry_run=True))
        self.style_button(self.btn_dry_run)

        self.btn_cancel = QPushButton("⏹ CANCEL", right_widget)
        self.btn_cancel.clicked.connect(self.cancel_execution)
        self.btn_cancel.setEnabled(False)
        self.style_button(self.btn_cancel, danger=True)

        exec_ctrl_layout.addWidget(self.btn_run_skill)
        exec_ctrl_layout.addWidget(self.btn_dry_run)
        exec_ctrl_layout.addWidget(self.btn_cancel)
        exec_ctrl_layout.addStretch()
        right_layout.addLayout(exec_ctrl_layout)

        # Progress bar
        self.progress_bar = QProgressBar(right_widget)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS['bg_input']};
                border: 1px solid {COLORS['border_subtle']};
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['cyan_glow']};
                border-radius: 3px;
            }}
        """)
        right_layout.addWidget(self.progress_bar)

        # Activity / Execution Log
        self.log_view = QTextEdit(right_widget)
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(140)
        self.log_view.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['bg_input']};
                border: 1px solid {COLORS['border_subtle']};
                border-radius: 4px;
                color: {COLORS['text_primary']};
                font-family: 'Consolas', monospace;
                font-size: 11px;
                padding: 6px;
            }}
        """)
        self.log_view.setPlaceholderText("Execution activity telemetry will appear here...")
        right_layout.addWidget(self.log_view)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)

    def style_button(self, btn: QPushButton, primary: bool = False, danger: bool = False):
        if primary:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['blue_accent']};
                    color: #ffffff;
                    border: 1px solid {COLORS['cyan_glow']};
                    border-radius: 4px;
                    padding: 6px 14px;
                    font-weight: bold;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['blue_hover']};
                }}
                QPushButton:disabled {{
                    background-color: #1a273b;
                    color: #4b6282;
                    border-color: #24354e;
                }}
            """)
        elif danger:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {COLORS['status_error']};
                    border: 1px solid {COLORS['status_error']};
                    border-radius: 4px;
                    padding: 6px 14px;
                    font-weight: bold;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: #3d141d;
                }}
                QPushButton:disabled {{
                    color: #4b6282;
                    border-color: #24354e;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['bg_panel_elevated']};
                    color: {COLORS['text_primary']};
                    border: 1px solid {COLORS['border_subtle']};
                    border-radius: 4px;
                    padding: 6px 14px;
                    font-weight: 600;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    border-color: {COLORS['cyan_glow']};
                    color: {COLORS['cyan_glow']};
                }}
                QPushButton:disabled {{
                    color: #4b6282;
                    border-color: #24354e;
                }}
            """)

    def reload_skills_list(self):
        self.skill_list.clear()
        skills = self.storage.get_all_skills()
        for s in skills:
            item = QListWidgetItem(f"{s.name}  [{len(s.steps)} steps]")
            item.setData(Qt.ItemDataRole.UserRole, s.id)
            if not s.enabled:
                item.setForeground(Qt.GlobalColor.darkGray)
            self.skill_list.addItem(item)

        if self.skill_list.count() > 0:
            self.skill_list.setCurrentRow(0)

    def filter_skills(self, text: str):
        query = text.strip().lower()
        for i in range(self.skill_list.count()):
            item = self.skill_list.item(i)
            item.setHidden(query not in item.text().lower())

    def on_skill_selected(self, current: Optional[QListWidgetItem], previous=None):
        if not current:
            self.current_skill = None
            self.skill_title_label.setText("Select a skill to view details")
            self.skill_desc_label.setText("")
            self.steps_table.setRowCount(0)
            return

        skill_id = current.data(Qt.ItemDataRole.UserRole)
        self.current_skill = self.storage.get_skill(skill_id)
        if not self.current_skill:
            return

        # Update details
        self.skill_title_label.setText(self.current_skill.name)
        self.skill_desc_label.setText(self.current_skill.description or "No description provided.")

        if self.current_skill.enabled:
            self.skill_status_badge.setText("ENABLED")
            self.skill_status_badge.setStyleSheet(f"color: {COLORS['status_success']}; font-weight: bold; border: 1px solid {COLORS['status_success']}; border-radius: 4px; padding: 4px 8px;")
        else:
            self.skill_status_badge.setText("DISABLED")
            self.skill_status_badge.setStyleSheet(f"color: {COLORS['status_error']}; font-weight: bold; border: 1px solid {COLORS['status_error']}; border-radius: 4px; padding: 4px 8px;")

        self.populate_steps_table()

    def populate_steps_table(self):
        if not self.current_skill:
            self.steps_table.setRowCount(0)
            return

        self.steps_table.setRowCount(len(self.current_skill.steps))
        for row, step in enumerate(self.current_skill.steps):
            item_order = QTableWidgetItem(str(step.order))
            item_order.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            item_type = QTableWidgetItem(step.action_type)
            item_label = QTableWidgetItem(step.label)
            item_args = QTableWidgetItem(json.dumps(step.arguments))
            item_confirm = QTableWidgetItem("YES" if step.require_confirmation else "NO")
            item_confirm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if step.require_confirmation:
                item_confirm.setForeground(Qt.GlobalColor.yellow)

            self.steps_table.setItem(row, 0, item_order)
            self.steps_table.setItem(row, 1, item_type)
            self.steps_table.setItem(row, 2, item_label)
            self.steps_table.setItem(row, 3, item_args)
            self.steps_table.setItem(row, 4, item_confirm)

    def on_create_skill(self):
        dialog = SkillDialog(self)
        if dialog.exec():
            self.storage.save_skill(dialog.skill)
            self.reload_skills_list()
            # Select new skill
            for i in range(self.skill_list.count()):
                if self.skill_list.item(i).data(Qt.ItemDataRole.UserRole) == dialog.skill.id:
                    self.skill_list.setCurrentRow(i)
                    break

    def on_edit_skill_meta(self):
        if not self.current_skill:
            return
        dialog = SkillDialog(self, skill=self.current_skill)
        if dialog.exec():
            self.storage.save_skill(dialog.skill)
            self.reload_skills_list()

    def on_duplicate_skill(self):
        if not self.current_skill:
            return
        clone = self.storage.duplicate_skill(self.current_skill.id)
        if clone:
            self.reload_skills_list()
            for i in range(self.skill_list.count()):
                if self.skill_list.item(i).data(Qt.ItemDataRole.UserRole) == clone.id:
                    self.skill_list.setCurrentRow(i)
                    break

    def on_delete_skill(self):
        if not self.current_skill:
            return
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to permanently delete workflow '{self.current_skill.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.storage.delete_skill(self.current_skill.id)
            self.reload_skills_list()

    def on_toggle_enable(self):
        if not self.current_skill:
            return
        new_state = not self.current_skill.enabled
        self.storage.set_skill_enabled(self.current_skill.id, new_state)
        self.current_skill.enabled = new_state
        self.reload_skills_list()

    def on_add_step(self):
        if not self.current_skill:
            QMessageBox.information(self, "No Skill Selected", "Please select or create a skill first.")
            return

        next_order = len(self.current_skill.steps) + 1
        dialog = StepDialog(self, registry=self.registry, step_order=next_order)
        if dialog.exec() and dialog.step:
            self.current_skill.steps.append(dialog.step)
            self.storage.save_skill(self.current_skill)
            self.populate_steps_table()

    def on_edit_step(self):
        row = self.steps_table.currentRow()
        if row < 0 or not self.current_skill or row >= len(self.current_skill.steps):
            return

        step = self.current_skill.steps[row]
        dialog = StepDialog(self, registry=self.registry, step=step)
        if dialog.exec():
            self.storage.save_skill(self.current_skill)
            self.populate_steps_table()

    def on_delete_step(self):
        row = self.steps_table.currentRow()
        if row < 0 or not self.current_skill or row >= len(self.current_skill.steps):
            return

        del self.current_skill.steps[row]
        # Re-index remaining steps
        for i, s in enumerate(self.current_skill.steps):
            s.order = i + 1

        self.storage.save_skill(self.current_skill)
        self.populate_steps_table()

    def on_move_step_up(self):
        row = self.steps_table.currentRow()
        if row <= 0 or not self.current_skill:
            return

        self.current_skill.steps[row], self.current_skill.steps[row - 1] = (
            self.current_skill.steps[row - 1], self.current_skill.steps[row]
        )
        for i, s in enumerate(self.current_skill.steps):
            s.order = i + 1

        self.storage.save_skill(self.current_skill)
        self.populate_steps_table()
        self.steps_table.selectRow(row - 1)

    def on_move_step_down(self):
        row = self.steps_table.currentRow()
        if not self.current_skill or row < 0 or row >= len(self.current_skill.steps) - 1:
            return

        self.current_skill.steps[row], self.current_skill.steps[row + 1] = (
            self.current_skill.steps[row + 1], self.current_skill.steps[row]
        )
        for i, s in enumerate(self.current_skill.steps):
            s.order = i + 1

        self.storage.save_skill(self.current_skill)
        self.populate_steps_table()
        self.steps_table.selectRow(row + 1)

    def start_execution(self, dry_run: bool = False):
        if not self.current_skill:
            return

        if not self.current_skill.enabled:
            QMessageBox.warning(
                self,
                "Execution Prevented",
                f"Cannot execute '{self.current_skill.name}' because it is currently disabled. Toggle enabled status first."
            )
            return

        # Prepare UI
        mode_label = "DRY-RUN (TEST PREVIEW)" if dry_run else "LIVE WORKFLOW"
        self.log_view.clear()
        self.log_view.append(f"[{mode_label} STARTED] Initializing {self.current_skill.name} ({len(self.current_skill.steps)} steps)...")

        self.btn_run_skill.setEnabled(False)
        self.btn_dry_run.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)

        # Worker
        self.worker = SkillWorker(self.engine, self.current_skill, dry_run=dry_run)
        self.worker.step_progress_signal.connect(self.on_step_progress)
        self.worker.workflow_finished_signal.connect(self.on_workflow_finished)
        self.worker.request_confirmation_signal.connect(self.on_request_confirmation)
        self.worker.start()

    def cancel_execution(self):
        if self.worker:
            self.log_view.append("[ABORT REQUESTED] Sending cancellation signal to engine...")
            self.worker.cancel()
            self.btn_cancel.setEnabled(False)

    def on_step_progress(self, step_id: str, status: str, msg: str):
        self.log_view.append(f"[{status}] {msg}")
        if not self.current_skill or not self.current_skill.steps:
            return

        # Estimate progress percentage
        current_step_order = 1
        for s in self.current_skill.steps:
            if s.id == step_id:
                current_step_order = s.order
                break

        total = len(self.current_skill.steps)
        progress = int((current_step_order / total) * 100)
        self.progress_bar.setValue(progress)

    def on_request_confirmation(self, step_id: str, prompt: str):
        reply = QMessageBox.question(
            self,
            "Security Confirmation Required",
            f"O.M.E.N. requires authorization to execute this sensitive workflow step:\n\n{prompt}\n\nDo you authorize execution?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if self.worker:
            self.worker.confirmation_response = (reply == QMessageBox.StandardButton.Yes)

    def on_workflow_finished(self, result: SkillExecutionResult):
        self.btn_run_skill.setEnabled(True)
        self.btn_dry_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)

        outcome_color = COLORS["status_success"] if result.success else COLORS["status_error"]
        mode_str = "DRY-RUN COMPLETE" if result.is_dry_run else f"WORKFLOW {result.status}"

        self.log_view.append(f"\n==================================================")
        self.log_view.append(f"RESULT: {mode_str} in {result.completed_at}")
        if result.error_message:
            self.log_view.append(f"ERROR: {result.error_message}")
        self.log_view.append(f"==================================================")

        self.progress_bar.setValue(100 if result.success else 0)
