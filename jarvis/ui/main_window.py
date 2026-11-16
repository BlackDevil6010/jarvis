"""Main GUI window for JARVIS desktop application with Holographic Glassmorphism Interface."""

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import (
    QIcon, QPixmap, QShortcut, QKeySequence, QPainter, QColor, QBrush,
    QLinearGradient, QRadialGradient, QAction
)
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QStackedWidget,
    QSystemTrayIcon, QMenu, QApplication
)

from jarvis.config import APP_NAME, APP_SUBTITLE, APP_VERSION, COLORS, LOGO_PATH, ICO_PATH
from jarvis.core.command_processor import CommandProcessor, CommandResponse
from jarvis.ui.styles import CYBER_STYLE
from jarvis.ui.widgets.status_indicator import StatusBadge
from jarvis.ui.widgets.console_view import ConsoleView
from jarvis.ui.widgets.voice_mic_widget import VoiceMicWidget
from jarvis.ui.widgets.holographic_header import HolographicHeader
from jarvis.ui.widgets.holographic_core import HolographicCoreWidget
from jarvis.ui.widgets.now_playing_widget import NowPlayingWidget
from jarvis.ui.widgets.media_quick_deck import MediaQuickDeck
from jarvis.ui.widgets.system_deck import SystemDeckWidget
from jarvis.ui.widgets.holographic_dock import HolographicDock
from jarvis.ui.skills.skill_forge_view import SkillForgeView
from jarvis.voice import VoiceController, VoiceState


class CommandWorker(QThread):
    """Executes commands asynchronously to keep the GUI fluid and responsive."""
    response_ready = Signal(object)

    def __init__(self, processor: CommandProcessor, command_text: str):
        super().__init__()
        self.processor = processor
        self.command_text = command_text

    def run(self):
        response = self.processor.process(self.command_text)
        self.response_ready.emit(response)


class MainWindow(QMainWindow):
    """Primary HUD window for JARVIS with Holographic Glassmorphism interface."""

    def __init__(self, processor: CommandProcessor = None):
        super().__init__()
        self.processor = processor or CommandProcessor()
        self.active_worker = None
        self._last_command_from_voice = False
        self.voice_controller = None

        # Cosmic star positions for space background
        self._star_positions = [
            (0.08, 0.15, 2), (0.18, 0.45, 1), (0.28, 0.12, 2), (0.35, 0.78, 1),
            (0.48, 0.22, 2), (0.62, 0.08, 1), (0.72, 0.35, 2), (0.85, 0.18, 1),
            (0.92, 0.65, 2), (0.12, 0.82, 1), (0.22, 0.92, 2), (0.55, 0.88, 1),
            (0.78, 0.75, 2), (0.88, 0.90, 1), (0.05, 0.55, 1), (0.95, 0.40, 2),
        ]

        self.db = getattr(self.processor, "db", None) or Database()

        self.init_window_properties()
        self.init_ui()
        self.init_voice()

    def init_window_properties(self):
        self.setWindowTitle(f"{APP_NAME} - {APP_SUBTITLE} [{APP_VERSION}]")
        self.resize(1180, 780)
        self.setMinimumSize(960, 640)
        self.setStyleSheet(CYBER_STYLE)

        icon_path = ICO_PATH if ICO_PATH.exists() else LOGO_PATH
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def init_ui(self):
        # Initialize background reminder monitoring with tray alerts
        from jarvis.core.reminders import ReminderManager
        self.reminder_mgr = ReminderManager(self.db, on_trigger=self._on_reminder_triggered)
        self.reminder_mgr.start()

        central_widget = QWidget(self)
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(6, 6, 6, 8)
        main_layout.setSpacing(6)

        # 1. Top Holographic Header Bar
        self.header = HolographicHeader(self)
        self.header.nav_requested.connect(self.switch_view)
        self.header.minimize_requested.connect(self.showMinimized)
        self.header.maximize_requested.connect(self._toggle_maximize)
        self.header.close_requested.connect(self.close)
        main_layout.addWidget(self.header)

        # Direct navigation and brand aliases for test compatibility
        self.logo_label = self.header.logo_label
        self.nav_hud_btn = self.header.btn_hud
        self.nav_skills_btn = self.header.btn_skills

        # 2. Main Stacked Content Area (Page 0: Holographic HUD, Page 1: Skill Forge)
        self.stacked_widget = QStackedWidget(self)

        # ==========================================
        # PAGE 0: Holographic Directives HUD
        # ==========================================
        hud_page = QWidget()
        hud_layout = QHBoxLayout(hud_page)
        hud_layout.setContentsMargins(10, 4, 10, 4)
        hud_layout.setSpacing(12)

        # --- LEFT WING ---
        left_wing = QVBoxLayout()
        left_wing.setSpacing(10)

        self.now_playing_card = NowPlayingWidget(hud_page)
        self.now_playing_card.mic_toggle_requested.connect(self.on_voice_mic_clicked)
        self.now_playing_card.stop_tts_requested.connect(self.on_voice_stop_clicked)
        self.now_playing_card.action_requested.connect(self._on_media_action)
        left_wing.addWidget(self.now_playing_card)

        self.media_deck = MediaQuickDeck(hud_page)
        self.media_deck.action_requested.connect(self.execute_command)
        left_wing.addWidget(self.media_deck)

        hud_layout.addLayout(left_wing, stretch=3)

        # --- CENTER WING: Segmented Holographic Core ---
        center_wing = QVBoxLayout()
        center_wing.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_wing.setSpacing(0)

        self.core_widget = HolographicCoreWidget(hud_page)
        self.core_widget.command_submitted.connect(self.execute_command)
        center_wing.addWidget(self.core_widget)

        hud_layout.addLayout(center_wing, stretch=4)

        # Expose command_input & send_button aliases for external & test access
        self.command_input = self.core_widget.input_field
        self.send_button = self.core_widget.btn_exec

        # --- RIGHT WING ---
        right_wing = QVBoxLayout()
        right_wing.setSpacing(10)

        # Neural AI Console Card
        self.console_card = QFrame(hud_page)
        self.console_card.setObjectName("ConsoleCard")
        console_card_layout = QVBoxLayout(self.console_card)
        console_card_layout.setContentsMargins(10, 8, 10, 8)
        console_card_layout.setSpacing(4)

        console_header = QHBoxLayout()
        c_title = QLabel("Neural AI Console", self.console_card)
        c_title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {COLORS['cyan_glow']}; letter-spacing: 1px;")
        console_header.addWidget(c_title)
        console_header.addStretch()

        self.status_badge = StatusBadge(self.console_card)
        console_header.addWidget(self.status_badge)
        console_card_layout.addLayout(console_header)

        self.console_view = ConsoleView(self.console_card)
        console_card_layout.addWidget(self.console_view, stretch=1)
        right_wing.addWidget(self.console_card, stretch=3)

        # System Telemetry Deck
        self.system_deck = SystemDeckWidget(hud_page)
        self.system_deck.action_requested.connect(self.execute_command)
        right_wing.addWidget(self.system_deck, stretch=2)

        hud_layout.addLayout(right_wing, stretch=4)

        self.stacked_widget.addWidget(hud_page)

        # ==========================================
        # PAGE 1: Skill Forge View
        # ==========================================
        self.skill_forge_view = SkillForgeView(self)
        self.stacked_widget.addWidget(self.skill_forge_view)

        main_layout.addWidget(self.stacked_widget, stretch=1)

        # 3. Bottom Floating Holographic Dock
        self.dock = HolographicDock(self)
        self.dock.home_clicked.connect(lambda: self.switch_view(0))
        self.dock.mic_clicked.connect(self.on_voice_mic_clicked)
        self.dock.skills_clicked.connect(lambda: self.switch_view(1))
        self.dock.music_clicked.connect(lambda: self.execute_command("open spotify"))
        self.dock.apps_clicked.connect(lambda: self.execute_command("list apps"))
        self.dock.diagnostics_clicked.connect(lambda: self.execute_command("diagnostics"))
        self.dock.settings_clicked.connect(lambda: self.execute_command("status"))
        main_layout.addWidget(self.dock)

        # Voice mic widget instance for state tracking
        self.voice_widget = VoiceMicWidget(self)
        self.voice_widget.setVisible(False)

        # Push-to-talk shortcut (Ctrl+Space) and cancel shortcut (Escape)
        self.ptt_shortcut = QShortcut(QKeySequence("Ctrl+Space"), self)
        self.ptt_shortcut.activated.connect(self.on_voice_mic_clicked)

        self.cancel_shortcut = QShortcut(QKeySequence("Escape"), self)
        self.cancel_shortcut.activated.connect(self.on_voice_stop_clicked)

        # System Tray Support
        self.tray_icon = None
        self._force_quit = False
        import os
        if QSystemTrayIcon.isSystemTrayAvailable() and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            icon_file = ICO_PATH if ICO_PATH.exists() else LOGO_PATH
            if icon_file.exists():
                self.tray_icon = QSystemTrayIcon(QIcon(str(icon_file)), self)
                self.tray_icon.setToolTip("O.M.E.N. Standing by • Call 'Hey Omen'")

                tray_menu = QMenu()
                show_act = QAction("🛰 Show O.M.E.N.", self)
                show_act.triggered.connect(self.show_and_activate)
                tray_menu.addAction(show_act)

                wake_act = QAction("🎙 Wake-Word: Active ('Hey Omen')", self)
                wake_act.setEnabled(False)
                tray_menu.addAction(wake_act)

                tray_menu.addSeparator()
                exit_act = QAction("✕ Exit", self)
                exit_act.triggered.connect(self._force_quit_app)
                tray_menu.addAction(exit_act)

                self.tray_icon.setContextMenu(tray_menu)
                self.tray_icon.activated.connect(self._on_tray_activated)
                self.tray_icon.show()

        # Default focus to central search input
        self.command_input.setFocus()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible() and not self.isMinimized():
                self.hide()
            else:
                self.show_and_activate()

    def show_and_activate(self):
        """Force window to restore, come to foreground, and take active focus."""
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

        # Windows-specific foreground window bypass (user32.dll)
        try:
            import ctypes
            hwnd = int(self.winId())
            if ctypes.windll.user32.IsIconic(hwnd):
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            else:
                ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.SwitchToThisWindow(hwnd, True)
        except Exception:
            pass

    def _force_quit_app(self):
        self._force_quit = True
        if hasattr(self, "voice_controller") and self.voice_controller:
            self.voice_controller.shutdown()
        QApplication.quit()

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def switch_view(self, index: int):
        self.stacked_widget.setCurrentIndex(index)
        self.header.set_nav_index(index)
        if index == 1:
            self.skill_forge_view.reload_skills_list()
        else:
            self.command_input.setFocus()

    def _on_media_action(self, action: str):
        if action == "prev":
            self.execute_command("skip track back")
        elif action == "next":
            self.execute_command("skip track")
        elif action == "play":
            self.execute_command("resume music")
        elif action == "pause":
            self.execute_command("pause music")

    def init_voice(self):
        """Initialize the asynchronous voice interaction subsystem."""
        self._last_command_from_voice = False
        try:
            self.voice_controller = VoiceController(
                command_processor=self.processor,
                enable_tts=True,
                auto_process_commands=False,
                parent=self
            )
            self.voice_controller.state_changed.connect(self.on_voice_state_changed)
            self.voice_controller.transcript_preview.connect(self.on_voice_transcript_preview)
            self.voice_controller.command_dispatched.connect(self.on_voice_command_dispatched)
            self.voice_controller.error_message.connect(self.on_voice_error)
            self.voice_controller.wake_word_triggered.connect(self.on_wake_word_activated)

            # Activate wake-word background listening ("Hey Jarvis")
            self.voice_controller.wake_word.enable()
        except Exception as exc:
            self.console_view.append_assistant_response(
                text=f"Voice Subsystem notice: {exc}",
                success=False,
                action_type="error"
            )

    def on_wake_word_activated(self, command_text: str = ""):
        """Wake up JARVIS: restore/raise window to front, acknowledge, and listen or execute."""
        # 1. Bring window to front
        self.show_and_activate()

        # 2. If directive was spoken alongside wake-word (e.g. "Hey Jarvis, open Spotify")
        clean_cmd = (command_text or "").strip()
        if clean_cmd:
            self.console_view.append_assistant_response(
                text=f"Wake-word triggered. Processing directive: \"{clean_cmd}\"",
                success=True,
                action_type="info"
            )
            self.execute_command(clean_cmd, from_voice=True)
        else:
            # 3. Only "Hey Jarvis" was spoken -> Vocalize acknowledge and start listening for directive
            if self.voice_controller:
                self.voice_controller.speak("Yes, Sir?")
                QTimer.singleShot(700, self.on_voice_mic_clicked)

    def on_voice_mic_clicked(self):
        if self.voice_controller:
            self.voice_controller.toggle_listening()

    def on_voice_stop_clicked(self):
        if self.voice_controller:
            self.voice_controller.cancel_all()
        self.status_badge.set_state("ONLINE", "SYSTEM READY")
        self.dock.set_listening_state(False)
        self.now_playing_card.set_voice_state("IDLE")

    def on_voice_state_changed(self, state_str: str, meta: dict):
        try:
            state = VoiceState(state_str)
            self.voice_widget.update_state(state, meta)

            is_listening = (state == VoiceState.LISTENING)
            self.dock.set_listening_state(is_listening)
            self.now_playing_card.set_voice_state(state_str, meta.get("transcript", ""))

            if state == VoiceState.LISTENING:
                self.status_badge.set_state("EXECUTING", "LISTENING...")
            elif state == VoiceState.PROCESSING:
                self.status_badge.set_state("EXECUTING", "PROCESSING AUDIO...")
            elif state == VoiceState.SPEAKING:
                self.status_badge.set_state("ONLINE", "VOCALIZING...")
            elif state == VoiceState.ERROR:
                self.status_badge.set_state("ERROR", "MIC FAULT")
            else:
                self.status_badge.set_state("ONLINE", "SYSTEM READY")
        except Exception:
            pass

    def on_voice_transcript_preview(self, text: str):
        self.command_input.setText(text)
        self.now_playing_card.set_voice_state("LISTENING", text)

    def on_voice_command_dispatched(self, command_text: str):
        self.command_input.setText(command_text)
        self.execute_command(command_text, from_voice=True)

    def on_voice_error(self, err_msg: str):
        self.console_view.append_assistant_response(
            text=f"VOICE SUBSYSTEM NOTICE: {err_msg}",
            success=False,
            action_type="error"
        )

    def on_shortcut_requested(self, command: str):
        if command.lower() in ["skills", "skill forge", "open skill forge"]:
            self.switch_view(1)
        else:
            self.execute_command(command)

    def on_send_clicked(self):
        text = self.command_input.text().strip()
        if not text:
            return
        self.command_input.clear()
        self.execute_command(text, from_voice=False)

    def execute_command(self, command_text: str, from_voice: bool = False):
        self._last_command_from_voice = from_voice
        self.console_view.append_user_message(command_text)
        self.status_badge.set_state("THINKING")
        self.send_button.setEnabled(False)

        self.active_worker = CommandWorker(self.processor, command_text)
        self.active_worker.response_ready.connect(self.on_command_finished)
        self.active_worker.start()

    def on_command_finished(self, response: CommandResponse):
        self.send_button.setEnabled(True)
        self.command_input.setFocus()

        if not response.success:
            self.status_badge.set_state("ERROR", "DIRECTIVE FAILED" if response.action_type == "launch" else "COMMAND REJECTED")
        elif response.action_type == "launch":
            self.status_badge.set_state("SUCCESS", "OPERATION COMPLETE")
        else:
            self.status_badge.set_state("ONLINE", "SYSTEM READY")

        if response.action_type == "clear":
            self.console_view.clear_console()
        else:
            self.console_view.append_assistant_response(
                text=response.text,
                success=response.success,
                action_type=response.action_type
            )

        if self._last_command_from_voice and response.text and self.voice_controller:
            first_sentence = response.text.split("\n")[0].strip()
            self.voice_controller.speak(first_sentence)
        self._last_command_from_voice = False

    def paintEvent(self, event):
        """Paint cosmic deep space background with subtle starry specks and ambient light."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 1. Deep cosmic gradient
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(4, 7, 16))
        grad.setColorAt(0.5, QColor(9, 16, 36))
        grad.setColorAt(1.0, QColor(5, 9, 20))
        painter.fillRect(0, 0, w, h, QBrush(grad))

        # 2. Ambient radial glow behind central core
        radial = QRadialGradient(w / 2.0, h / 2.0, min(w, h) * 0.48)
        radial.setColorAt(0.0, QColor(0, 240, 255, 32))
        radial.setColorAt(0.6, QColor(138, 43, 226, 20))
        radial.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(0, 0, w, h, QBrush(radial))

        # 3. Ambient glow along the bottom dock
        dock_glow = QLinearGradient(0, h - 90, 0, h)
        dock_glow.setColorAt(0.0, QColor(0, 0, 0, 0))
        dock_glow.setColorAt(1.0, QColor(0, 240, 255, 18))
        painter.fillRect(0, h - 90, w, 90, QBrush(dock_glow))

        # 4. Subtle star specks
        painter.setPen(QColor(255, 255, 255, 95))
        for x, y, r in self._star_positions:
            px = int(x * w)
            py = int(y * h)
            painter.drawEllipse(px, py, r, r)

        painter.end()
        super().paintEvent(event)

    def _on_reminder_triggered(self, reminder_data: dict):
        """Handle background reminder countdown expiring."""
        msg = reminder_data.get("message", "Timer expired!")
        if self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                "⏰ O.M.E.N. Timer Expired",
                f"Directive Alert: {msg}",
                QSystemTrayIcon.MessageIcon.Information,
                5000
            )
        self.console_view.append_assistant_response(
            f"⏰ **TIMER ALERT:** {msg}",
            success=True,
            action_type="launch"
        )
        if hasattr(self, "voice_controller") and self.voice_controller and self.voice_controller.tts:
            self.voice_controller.tts.speak(f"Sir, your timer for {msg} has expired.")

    def closeEvent(self, event):
        import os
        if not self._force_quit and self.tray_icon and self.tray_icon.isVisible() and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            self.hide()
            self.tray_icon.showMessage(
                "O.M.E.N. Standing By",
                "Minimized to system tray. Say 'Hey Omen' anytime to wake up.",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            event.ignore()
        else:
            if hasattr(self, "reminder_mgr") and self.reminder_mgr:
                self.reminder_mgr.stop()
            if hasattr(self, "voice_controller") and self.voice_controller:
                self.voice_controller.shutdown()
            super().closeEvent(event)
