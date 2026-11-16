"""Background wake-word detection engine for JARVIS.

Continuously monitors audio for "Hey Jarvis", "Jarvis", or "OK Jarvis"
in a lightweight daemon thread, restoring and activating the assistant
without requiring manual clicks.
"""

import time
import logging
import threading
from typing import Optional, List
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class WakeWordController(QObject):
    """
    Manages continuous background wake-word monitoring.
    Emits wake_word_detected with any trailing directive text.
    """

    wake_word_detected = Signal(str)
    enabled_changed = Signal(bool)
    status_changed = Signal(str)

    DEFAULT_WAKE_WORDS = ["hey omen", "omen", "ok omen", "hello omen", "hi omen", "hey jarvis", "jarvis"]

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._enabled = False
        self._paused = False
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._wake_words = list(self.DEFAULT_WAKE_WORDS)

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def is_paused(self) -> bool:
        return self._paused

    def enable(self) -> bool:
        """Activate continuous background wake-word listening thread."""
        if self._enabled and self._worker_thread and self._worker_thread.is_alive():
            return True

        self._enabled = True
        self._paused = False
        self._stop_event.clear()

        self._worker_thread = threading.Thread(
            target=self._listen_loop,
            name="OMEN-WakeWord-Thread",
            daemon=True
        )
        self._worker_thread.start()

        logger.info("Wake-word background monitoring activated ('Hey Omen', 'Omen').")
        self.enabled_changed.emit(True)
        self.status_changed.emit("Wake-word active: Listening for 'Hey Omen'")
        return True

    def disable(self) -> None:
        """Halt the background listening thread."""
        self._enabled = False
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        self._worker_thread = None

        logger.info("Wake-word monitoring deactivated.")
        self.enabled_changed.emit(False)
        self.status_changed.emit("Wake-word deactivated")

    def pause(self) -> None:
        """Temporarily suspend wake-word listening (e.g. while mic is actively capturing directive or TTS is speaking)."""
        self._paused = True

    def resume(self) -> None:
        """Resume wake-word listening after active voice interaction concludes."""
        self._paused = False

    def check_text_for_wake_word(self, text: str) -> Optional[str]:
        """Check if recognized text contains or starts with a wake-word."""
        if not self._enabled or not text:
            return None
        text_lower = text.lower().strip()
        for ww in self._wake_words:
            if ww in text_lower:
                # Extract any command following the wake-word
                idx = text_lower.find(ww)
                remainder = text_lower[idx + len(ww):].strip()
                if remainder.startswith(",") or remainder.startswith(":"):
                    remainder = remainder[1:].strip()
                return remainder
        return None

    def _listen_loop(self) -> None:
        """Background daemon listening loop."""
        try:
            import speech_recognition as sr
        except ImportError:
            logger.warning("speech_recognition not installed. Wake-word detection unavailable.")
            self._enabled = False
            return

        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 400
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.6

        # Auto-detect best microphone
        try:
            from jarvis.voice.stt import SpeechRecognitionEngine
            dev_idx = SpeechRecognitionEngine.detect_best_microphone_index()
        except Exception:
            dev_idx = None

        mic_kwargs = {}
        if dev_idx is not None:
            mic_kwargs["device_index"] = dev_idx

        while self._enabled and not self._stop_event.is_set():
            if self._paused:
                time.sleep(0.25)
                continue

            try:
                with sr.Microphone(**mic_kwargs) as source:
                    # Quick ambient adjustment
                    recognizer.adjust_for_ambient_noise(source, duration=0.4)
                    if recognizer.energy_threshold < 300:
                        recognizer.energy_threshold = 300

                    while self._enabled and not self._stop_event.is_set():
                        if self._paused:
                            time.sleep(0.25)
                            continue

                        try:
                            audio = recognizer.listen(source, timeout=2.0, phrase_time_limit=3.5)
                        except sr.WaitTimeoutError:
                            continue

                        if self._paused or self._stop_event.is_set():
                            continue

                        # Recognize audio
                        try:
                            transcript = recognizer.recognize_google(audio, language="en-US").lower().strip()
                            logger.debug(f"WakeWord background heard: '{transcript}'")
                            
                            for ww in self._wake_words:
                                if ww in transcript:
                                    logger.info(f"Wake-word triggered by '{ww}' in '{transcript}'")
                                    # Extract remainder command
                                    idx = transcript.find(ww)
                                    trailing_cmd = transcript[idx + len(ww):].strip()
                                    if trailing_cmd.startswith(",") or trailing_cmd.startswith(":"):
                                        trailing_cmd = trailing_cmd[1:].strip()
                                    
                                    self.wake_word_detected.emit(trailing_cmd)
                                    # Pause briefly so recognition doesn't re-trigger itself
                                    time.sleep(1.0)
                                    break
                        except (sr.UnknownValueError, sr.RequestError):
                            pass

            except Exception as e:
                logger.warning(f"WakeWord listener mic loop error: {e}. Retrying in 2 seconds...")
                time.sleep(2.0)
