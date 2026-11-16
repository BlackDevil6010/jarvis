"""Unified Voice Controller for JARVIS.

Coordinates Speech-to-Text (STT), Text-to-Speech (TTS), Push-to-Talk,
Wake-Word detection, and safe directive routing through CommandProcessor.
"""

import logging
from typing import Optional, Dict, Any, Callable

from PySide6.QtCore import QObject, Signal, Slot

from jarvis.voice.state import VoiceState, VOICE_STATE_META
from jarvis.voice.tts import TextToSpeechEngine
from jarvis.voice.stt import SpeechRecognitionEngine
from jarvis.voice.wake_word import WakeWordController
from jarvis.core.command_processor import CommandProcessor, CommandResponse

logger = logging.getLogger(__name__)


class VoiceController(QObject):
    """
    Central coordinator of voice input and vocalized output.
    Bridges PySide6 UI, audio hardware, and existing security/command pipelines.
    """

    state_changed = Signal(str, dict)       # state_name, meta_dict
    transcript_preview = Signal(str)        # intermediate or finalized transcript
    command_dispatched = Signal(str)        # command sent to processor
    voice_response_ready = Signal(str)      # speech output response text
    error_message = Signal(str)             # human-readable error description
    wake_word_triggered = Signal(str)       # wake-word detected with optional trailing command

    def __init__(
        self,
        command_processor: Optional[CommandProcessor] = None,
        enable_tts: bool = True,
        auto_process_commands: bool = True,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.command_processor = command_processor or CommandProcessor()
        self.enable_tts = enable_tts
        self.auto_process_commands = auto_process_commands
        self._current_state = VoiceState.IDLE
        self._ptt_active = False

        # Subsystems
        self.stt = SpeechRecognitionEngine(self)
        self.tts = TextToSpeechEngine(parent=self)
        self.wake_word = WakeWordController(self)

        # Wire Wake-Word signals
        self.wake_word.wake_word_detected.connect(self._on_wake_word_detected)

        # Wire STT signals
        self.stt.state_changed.connect(self._on_stt_state_changed)
        self.stt.transcription_ready.connect(self._on_transcription_ready)
        self.stt.error_occurred.connect(self._on_stt_error)

        # Wire TTS signals
        self.tts.started.connect(self._on_tts_started)
        self.tts.finished.connect(self._on_tts_finished)
        self.tts.error.connect(self._on_tts_error)

    @Slot(str)
    def _on_wake_word_detected(self, command_text: str) -> None:
        """Handle wake-word trigger from background listener."""
        logger.info(f"VoiceController: Wake-word signal received with command: '{command_text}'")
        self.wake_word_triggered.emit(command_text)

    @property
    def current_state(self) -> VoiceState:
        return self._current_state

    def _update_state(self, new_state: VoiceState) -> None:
        """Update internal state and notify observers with visual metadata."""
        self._current_state = new_state
        meta = VOICE_STATE_META.get(new_state, {})
        self.state_changed.emit(new_state.value, meta)

        # Manage wake-word pause/resume based on active mic/speech state
        if new_state in [VoiceState.LISTENING, VoiceState.PROCESSING, VoiceState.SPEAKING]:
            self.wake_word.pause()
        elif new_state == VoiceState.IDLE:
            self.wake_word.resume()

    # -------------------------------------------------------------------------
    # Listening / Push-To-Talk Controls
    # -------------------------------------------------------------------------

    def toggle_listening(self) -> bool:
        """Toggle listening state (for single-click mic button)."""
        if self._current_state == VoiceState.LISTENING:
            self.stop_listening()
            return False
        elif self._current_state == VoiceState.SPEAKING:
            self.stop_speaking()
            return False
        else:
            return self.start_listening()

    def start_listening(self) -> bool:
        """Initiate audio capture from user microphone."""
        # Interrupt any current speech before listening
        if self.tts.is_speaking():
            self.tts.stop()

        success = self.stt.start_listening()
        if not success:
            logger.warning("VoiceController: Failed to start listening.")
        return success

    def stop_listening(self) -> None:
        """Halt active listening."""
        self.stt.stop_listening()

    def push_to_talk_pressed(self) -> None:
        """Triggered when Push-to-Talk shortcut key is depressed."""
        if not self._ptt_active:
            self._ptt_active = True
            self.start_listening()

    def push_to_talk_released(self) -> None:
        """Triggered when Push-to-Talk shortcut key is released."""
        if self._ptt_active:
            self._ptt_active = False
            self.stop_listening()

    # -------------------------------------------------------------------------
    # Speech Synthesis Controls
    # -------------------------------------------------------------------------

    def speak(self, text: str, interrupt: bool = True) -> None:
        """Vocalize response text through local audio output."""
        if not self.enable_tts:
            return
        self.tts.speak(text, interrupt=interrupt)

    def stop_speaking(self) -> None:
        """Immediately silence ongoing speech synthesis."""
        self.tts.stop()
        if self._current_state == VoiceState.SPEAKING:
            self._update_state(VoiceState.IDLE)

    def cancel_all(self) -> None:
        """Emergency stop: halts active audio capture, transcription, and speech."""
        self.stt.stop_listening()
        self.tts.stop()
        self._ptt_active = False
        self._update_state(VoiceState.IDLE)

    # -------------------------------------------------------------------------
    # Signal Handlers
    # -------------------------------------------------------------------------

    @Slot(str)
    def _on_stt_state_changed(self, state_str: str) -> None:
        try:
            state_enum = VoiceState(state_str)
            self._update_state(state_enum)
        except ValueError:
            pass

    @Slot(str)
    def _on_transcription_ready(self, recognized_text: str) -> None:
        """Handle incoming speech transcript from STT engine."""
        clean_text = recognized_text.strip()
        if not clean_text:
            self._update_state(VoiceState.IDLE)
            return

        logger.info(f"Voice recognized: '{clean_text}'")
        self.transcript_preview.emit(clean_text)

        # Check wake-word if wake-word monitoring is enabled
        effective_command = clean_text
        if self.wake_word.is_enabled:
            ww_result = self.wake_word.check_text_for_wake_word(clean_text)
            if ww_result:
                effective_command = ww_result

        # Route through existing CommandProcessor and security sandbox
        self.command_dispatched.emit(effective_command)
        if self.auto_process_commands:
            response: CommandResponse = self.command_processor.process(effective_command)

            # Emit vocal response if TTS is active
            if self.enable_tts and response and response.text:
                # Vocalize concise summary for clean auditory experience
                first_sentence = response.text.split("\n")[0].strip()
                self.speak(first_sentence)
                self.voice_response_ready.emit(response.text)

    @Slot(str)
    def _on_stt_error(self, err_msg: str) -> None:
        logger.error(f"STT Error: {err_msg}")
        self._update_state(VoiceState.ERROR)
        self.error_message.emit(err_msg)

    @Slot(str)
    def _on_tts_started(self, text: str) -> None:
        self._update_state(VoiceState.SPEAKING)

    @Slot()
    def _on_tts_finished(self) -> None:
        if self._current_state == VoiceState.SPEAKING:
            self._update_state(VoiceState.IDLE)

    @Slot(str)
    def _on_tts_error(self, err_msg: str) -> None:
        logger.error(f"TTS Error: {err_msg}")
        self._update_state(VoiceState.ERROR)
        self.error_message.emit(err_msg)

    def shutdown(self) -> None:
        """Clean shutdown of voice subsystems."""
        self.cancel_all()
        self.wake_word.disable()
        self.tts.shutdown()
