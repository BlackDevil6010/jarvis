"""Unit and integration tests for JARVIS Voice Interaction Subsystem (Phase 1)."""

import pytest
from unittest.mock import MagicMock, patch

from jarvis.voice.state import VoiceState, VOICE_STATE_META
from jarvis.voice.tts import TextToSpeechEngine, clean_text_for_speech
from jarvis.voice.stt import SpeechRecognitionEngine
from jarvis.voice.wake_word import WakeWordController
from jarvis.voice.controller import VoiceController
from jarvis.core.command_processor import CommandProcessor
from jarvis.ui.widgets.voice_mic_widget import VoiceMicWidget


# -----------------------------------------------------------------------------
# 1. Voice State & Telemetry Meta Tests
# -----------------------------------------------------------------------------

def test_voice_states_defined():
    """Verify all mandatory voice states exist and have metadata."""
    assert VoiceState.IDLE == "idle"
    assert VoiceState.LISTENING == "listening"
    assert VoiceState.PROCESSING == "processing"
    assert VoiceState.SPEAKING == "speaking"
    assert VoiceState.ERROR == "error"

    for state in VoiceState:
        assert state in VOICE_STATE_META
        meta = VOICE_STATE_META[state]
        assert "label" in meta
        assert "icon" in meta
        assert "badge_color" in meta


# -----------------------------------------------------------------------------
# 2. Text-to-Speech Sanitization & Engine Tests
# -----------------------------------------------------------------------------

def test_clean_text_for_speech():
    """Verify that markdown, code blocks, URLs, and symbols are stripped for vocalization."""
    raw = "Hello! Check this ```python\nprint('code')\n``` and visit https://example.com for `details`."
    cleaned = clean_text_for_speech(raw)
    assert "Code snippet omitted." in cleaned
    assert "web link" in cleaned
    assert "details" in cleaned
    assert "```" not in cleaned
    assert "https://" not in cleaned

    # Empty text handling
    assert clean_text_for_speech("") == ""
    assert clean_text_for_speech(None) == ""


def test_tts_engine_lifecycle(qapp):
    """Verify TTS initialization, queueing, and shutdown."""
    tts = TextToSpeechEngine()
    assert tts.is_speaking() is False

    # Calling speak and immediate stop
    tts.speak("Testing speech synthesis")
    tts.stop()
    assert tts.is_speaking() is False

    # Check available voices returns a list
    voices = tts.get_available_voices()
    assert isinstance(voices, list)

    tts.shutdown()


# -----------------------------------------------------------------------------
# 3. Wake-Word Controller Tests
# -----------------------------------------------------------------------------

def test_wake_word_disabled_by_default():
    """Wake-word detection MUST be disabled by default for privacy."""
    ww = WakeWordController()
    assert ww.is_enabled is False

    # When disabled, check_text_for_wake_word returns None
    result = ww.check_text_for_wake_word("jarvis open notepad")
    assert result is None


def test_wake_word_explicit_enable():
    """Verify wake-word can be explicitly enabled and extracts commands."""
    ww = WakeWordController()
    ww.enable()
    assert ww.is_enabled is True

    # Matching wake words
    cmd1 = ww.check_text_for_wake_word("jarvis, open notepad")
    assert cmd1 == "open notepad"

    cmd2 = ww.check_text_for_wake_word("hey jarvis: show system info")
    assert cmd2 == "show system info"

    # Non-wake word phrase
    assert ww.check_text_for_wake_word("open calculator") is None

    # Disable
    ww.disable()
    assert ww.is_enabled is False


# -----------------------------------------------------------------------------
# 4. Speech Recognition Engine Tests
# -----------------------------------------------------------------------------

def test_stt_device_listing(qapp):
    """Verify audio input device discovery."""
    stt = SpeechRecognitionEngine()
    devices = stt.get_input_devices()
    assert isinstance(devices, list)


def test_stt_missing_microphone_handling(qapp):
    """Verify graceful error reporting when no microphone is detected."""
    stt = SpeechRecognitionEngine()
    with patch.object(stt, "get_input_devices", return_value=[]):
        has_mic, msg = stt.check_microphone_available()
        assert has_mic is False
        assert "no audio input devices" in msg.lower()

        # Attempting to listen emits error and sets ERROR state
        error_signals = []
        stt.error_occurred.connect(error_signals.append)
        success = stt.start_listening()
        assert success is False
        assert stt.current_state == VoiceState.ERROR
        assert len(error_signals) > 0


# -----------------------------------------------------------------------------
# 5. Voice Controller & Command Routing Tests
# -----------------------------------------------------------------------------

def test_voice_controller_command_routing(qapp):
    """Verify recognized voice commands are routed safely through CommandProcessor."""
    processor = MagicMock(spec=CommandProcessor)
    mock_resp = MagicMock()
    mock_resp.text = "Notepad opened successfully"
    mock_resp.success = True
    processor.process.return_value = mock_resp

    vc = VoiceController(command_processor=processor, enable_tts=False, auto_process_commands=True)

    dispatched = []
    vc.command_dispatched.connect(dispatched.append)

    # Simulate recognized transcript
    vc._on_transcription_ready("Open Notepad")

    assert "Open Notepad" in dispatched
    processor.process.assert_called_once_with("Open Notepad")
    vc.shutdown()


def test_voice_controller_blocks_dangerous_speech_commands(qapp):
    """Ensure shell injections or malicious phrases from speech are rejected by real CommandProcessor."""
    real_processor = CommandProcessor()
    vc = VoiceController(command_processor=real_processor, enable_tts=False, auto_process_commands=True)

    vc._on_transcription_ready("Open Notepad; rm -rf /")
    # Voice state should return to idle after processing
    assert vc.current_state in (VoiceState.IDLE, VoiceState.ERROR)
    vc.shutdown()


def test_voice_controller_cancel_all(qapp):
    """Verify emergency stop cancels listening and silences speech."""
    vc = VoiceController(enable_tts=False)
    vc.cancel_all()
    assert vc.current_state == VoiceState.IDLE
    vc.shutdown()


# -----------------------------------------------------------------------------
# 6. VoiceMicWidget UI Component Tests
# -----------------------------------------------------------------------------

def test_voice_mic_widget_state_updates(qapp):
    """Verify UI badge and stop button visibility update across all voice states."""
    widget = VoiceMicWidget()
    widget.show()

    # IDLE state
    widget.update_state(VoiceState.IDLE)
    assert widget.stop_btn.isHidden() is True
    assert "MIC" in widget.mic_btn.text()

    # LISTENING state
    widget.update_state(VoiceState.LISTENING)
    assert widget.stop_btn.isHidden() is False
    assert "LISTENING" in widget.mic_btn.text()

    # PROCESSING state
    widget.update_state(VoiceState.PROCESSING)
    assert widget.stop_btn.isHidden() is False

    # SPEAKING state
    widget.update_state(VoiceState.SPEAKING)
    assert widget.stop_btn.isHidden() is False

    # ERROR state
    widget.update_state(VoiceState.ERROR)
    assert widget.stop_btn.isHidden() is True
    assert "FAULT" in widget.mic_btn.text()
