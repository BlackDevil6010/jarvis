"""Asynchronous Text-to-Speech (TTS) synthesizer for JARVIS using local SAPI5."""

import re
import queue
import logging
import threading
from typing import Optional, List, Dict, Any

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


def clean_text_for_speech(raw_text: str) -> str:
    """Strip markdown formatting, code fences, and symbols for natural vocalization."""
    if not raw_text:
        return ""
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", " Code snippet omitted. ", raw_text)
    # Remove inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove URLs
    text = re.sub(r"https?://\S+", " web link ", text)
    # Remove markdown headers and bullets
    text = re.sub(r"[#*_~>]+", "", text)
    # Remove ASCII tables or divider lines
    text = re.sub(r"[-=]{3,}", "", text)
    # Collapse multiple whitespaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


class TextToSpeechEngine(QObject):
    """
    Non-blocking Text-to-Speech engine utilizing local Windows speech synthesis.
    Executes synthesis operations in a dedicated daemon worker thread.
    """

    started = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, rate: int = 185, volume: float = 0.95, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.rate = rate
        self.volume = max(0.0, min(1.0, volume))
        self._speech_queue: queue.Queue = queue.Queue()
        self._is_speaking = False
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = True
        self._start_worker()

    def _start_worker(self) -> None:
        """Launch the background speech worker thread."""
        self._worker_thread = threading.Thread(target=self._speech_loop, daemon=True)
        self._worker_thread.start()

    def _speech_loop(self) -> None:
        """Dedicated worker thread loop managing SAPI5 voice engine."""
        # Initialize COM library for the current thread on Windows
        try:
            import pythoncom
            has_com = True
        except ImportError:
            has_com = False

        engine = None
        try:
            if has_com:
                pythoncom.CoInitialize()
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)
        except Exception as exc:
            logger.warning(f"Failed to initialize pyttsx3 engine: {exc}")
            self.error.emit(f"Speech synthesis initialization error: {exc}")

        while self._running:
            try:
                # Wait for next text item to speak
                item = self._speech_queue.get(timeout=0.25)
            except queue.Empty:
                continue

            if item is None:  # Sentinel value for shutdown
                break

            text_to_speak = item
            self._stop_event.clear()
            self._is_speaking = True
            self.started.emit(text_to_speak)

            try:
                if engine:
                    # Clean text and speak
                    cleaned = clean_text_for_speech(text_to_speak)
                    if cleaned:
                        engine.say(cleaned)
                        engine.runAndWait()
                else:
                    logger.debug(f"[TTS Fallback Sim] Spoke: {text_to_speak}")
            except Exception as exc:
                logger.error(f"TTS synthesis error: {exc}")
                self.error.emit(f"Voice playback error: {exc}")
            finally:
                self._is_speaking = False
                self.finished.emit()
                self._speech_queue.task_done()

        if engine:
            try:
                engine.stop()
            except Exception:
                pass
        if has_com:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def speak(self, text: str, interrupt: bool = True) -> None:
        """
        Queue text for vocalization.
        If interrupt is True, flushes any currently speaking or queued utterances.
        """
        if not text or not text.strip():
            return

        if interrupt:
            self.stop()

        self._speech_queue.put(text.strip())

    def stop(self) -> None:
        """Stop current speech immediately and flush queue."""
        self._stop_event.set()
        # Drain queue
        while not self._speech_queue.empty():
            try:
                self._speech_queue.get_nowait()
                self._speech_queue.task_done()
            except (queue.Empty, ValueError):
                break
        self._is_speaking = False

    def is_speaking(self) -> bool:
        """Return True if currently synthesizing or vocalizing."""
        return self._is_speaking

    def get_available_voices(self) -> List[Dict[str, Any]]:
        """Return list of available local TTS voices."""
        voices = []
        try:
            import pyttsx3
            eng = pyttsx3.init()
            for v in eng.getProperty("voices"):
                voices.append({
                    "id": v.id,
                    "name": v.name,
                    "languages": getattr(v, "languages", []),
                    "gender": getattr(v, "gender", "unknown")
                })
        except Exception as exc:
            logger.warning(f"Failed to query local voices: {exc}")
        return voices

    def shutdown(self) -> None:
        """Gracefully terminate background speech thread."""
        self._running = False
        self.stop()
        self._speech_queue.put(None)
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
