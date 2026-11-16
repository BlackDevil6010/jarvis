"""Voice state definitions and UI telemetry constants for JARVIS."""

from enum import Enum
from typing import Dict, Any


class VoiceState(str, Enum):
    """Lifecycle states of the voice interaction subsystem."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


VOICE_STATE_META: Dict[VoiceState, Dict[str, Any]] = {
    VoiceState.IDLE: {
        "label": "MIC READY",
        "description": "Voice subsystem is standing by. Press Mic or PTT hotkey to speak.",
        "badge_color": "#24354E",
        "text_color": "#8BA2C1",
        "icon": "🎙",
    },
    VoiceState.LISTENING: {
        "label": "LISTENING...",
        "description": "Capturing speech audio input from microphone...",
        "badge_color": "#00E5FF",
        "text_color": "#050B14",
        "icon": "🔴",
    },
    VoiceState.PROCESSING: {
        "label": "PROCESSING...",
        "description": "Transcribing speech audio and parsing directives...",
        "badge_color": "#FFC107",
        "text_color": "#050B14",
        "icon": "⚡",
    },
    VoiceState.SPEAKING: {
        "label": "SPEAKING...",
        "description": "Vocalizing assistant response through audio output.",
        "badge_color": "#00E5FF",
        "text_color": "#050B14",
        "icon": "🔊",
    },
    VoiceState.ERROR: {
        "label": "MIC FAULT",
        "description": "An audio or transcription error was encountered.",
        "badge_color": "#FF3366",
        "text_color": "#FFFFFF",
        "icon": "⚠",
    },
}
