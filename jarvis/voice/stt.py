"""Speech-to-Text (STT) capture and transcription engine for JARVIS.

Features intelligent audio device selection, signal level metering,
online Google STT with language support, offline Vosk discovery,
and clear diagnostic error reporting.
"""

import os
import json
import logging
import struct
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from PySide6.QtCore import QObject, Signal
from jarvis.voice.state import VoiceState

logger = logging.getLogger(__name__)


def calculate_rms_level(raw_bytes: bytes) -> float:
    """Calculate normalized Root-Mean-Square audio energy (0.0 to 1.0)."""
    if not raw_bytes or len(raw_bytes) < 2:
        return 0.0
    count = len(raw_bytes) // 2
    format_str = f"<{count}h"
    try:
        shorts = struct.unpack(format_str, raw_bytes[:count * 2])
        sum_squares = sum(s * s for s in shorts)
        rms = (sum_squares / count) ** 0.5
        # Normalize: 0 to ~32767 mapped to 0.0 - 1.0
        return min(1.0, rms / 32767.0)
    except Exception:
        return 0.0


class SpeechRecognitionEngine(QObject):
    """
    Speech recognition engine supporting live microphone capture,
    online Google STT, and optional local offline Vosk models.
    Operates asynchronously to keep PySide6 GUI responsive.
    """

    state_changed = Signal(str)            # VoiceState string
    transcription_ready = Signal(str)      # Recognized text
    error_occurred = Signal(str)           # Error message
    audio_level = Signal(float)            # RMS energy / level (0.0 to 1.0)
    listening_finished = Signal()

    def __init__(self, parent: Optional[QObject] = None, language: str = "en-US"):
        super().__init__(parent)
        self.language = language
        self._current_state = VoiceState.IDLE
        self._stop_listening_flag = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._device_index: Optional[int] = None
        self._vosk_model_path: Optional[str] = self._discover_vosk_model()

    def _discover_vosk_model(self) -> Optional[str]:
        """Locate an optional offline Vosk model in standard directories."""
        candidate_paths = [
            Path("data/models/vosk"),
            Path("models/vosk"),
            Path(os.environ.get("VOSK_MODEL_PATH", "")),
        ]
        for p in candidate_paths:
            if p and p.is_dir() and ((p / "am").exists() or (p / "README").exists()):
                return str(p.resolve())
        return None

    @property
    def current_state(self) -> VoiceState:
        return self._current_state

    def _set_state(self, state: VoiceState) -> None:
        self._current_state = state
        self.state_changed.emit(state.value)

    def get_input_devices(self) -> List[Dict[str, Any]]:
        """Return all detected audio input devices and their indices."""
        devices = []
        try:
            import speech_recognition as sr
            mic_names = sr.Microphone.list_microphone_names()
            for idx, name in enumerate(mic_names):
                devices.append({
                    "index": idx,
                    "name": name,
                })
        except Exception as exc:
            logger.warning(f"Failed to query microphone devices: {exc}")
        return devices

    def check_microphone_available(self) -> Tuple[bool, str]:
        """Verify that at least one valid audio input device is available."""
        devices = self.get_input_devices()
        if not devices:
            return False, "No audio input devices detected on this system."
        return True, f"Found {len(devices)} audio device(s)."

    def detect_best_microphone_index(self) -> Optional[int]:
        """Auto-detect the active physical microphone index."""
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            try:
                default_info = p.get_default_input_device_info()
                def_index = default_info.get("index")
                if def_index is not None:
                    p.terminate()
                    return int(def_index)
            except Exception:
                pass

            # Search for real input device with channels > 0
            for idx in range(p.get_device_count()):
                info = p.get_device_info_by_index(idx)
                if info.get("maxInputChannels", 0) > 0:
                    name = info.get("name", "").lower()
                    if any(k in name for k in ["realtek", "microphone", "headset", "usb audio"]):
                        p.terminate()
                        return idx
            p.terminate()
        except Exception as exc:
            logger.debug(f"Could not auto-detect microphone index: {exc}")
        return None

    def start_listening(self, phrase_time_limit: int = 8, timeout: int = 5) -> bool:
        """
        Begin listening on a background thread.
        Returns False if microphone is unavailable or already listening.
        """
        if self._current_state in (VoiceState.LISTENING, VoiceState.PROCESSING):
            logger.warning("Listening operation already active.")
            return False

        has_mic, mic_msg = self.check_microphone_available()
        if not has_mic:
            self._set_state(VoiceState.ERROR)
            self.error_occurred.emit(f"Microphone unavailable: {mic_msg}")
            return False

        self._stop_listening_flag.clear()
        self._set_state(VoiceState.LISTENING)

        self._worker_thread = threading.Thread(
            target=self._listen_worker,
            args=(phrase_time_limit, timeout),
            daemon=True
        )
        self._worker_thread.start()
        return True

    def stop_listening(self) -> None:
        """Signal background listening thread to stop immediately."""
        self._stop_listening_flag.set()
        if self._current_state == VoiceState.LISTENING:
            self._set_state(VoiceState.IDLE)
            self.listening_finished.emit()

    def _listen_worker(self, phrase_time_limit: int, timeout: int) -> None:
        """Background worker thread capturing audio and dispatching to recognizer."""
        try:
            import speech_recognition as sr
        except ImportError:
            self._set_state(VoiceState.ERROR)
            self.error_occurred.emit("Speech recognition library not installed.")
            self.listening_finished.emit()
            return

        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 400
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.8

        audio_data = None
        device_idx = self._device_index
        if device_idx is None:
            device_idx = self.detect_best_microphone_index()

        try:
            mic_kwargs = {}
            if device_idx is not None:
                mic_kwargs["device_index"] = device_idx

            with sr.Microphone(**mic_kwargs) as source:
                # Ambient noise calibration
                recognizer.adjust_for_ambient_noise(source, duration=0.6)
                if recognizer.energy_threshold < 300:
                    recognizer.energy_threshold = 300

                if self._stop_listening_flag.is_set():
                    self._set_state(VoiceState.IDLE)
                    self.listening_finished.emit()
                    return

                try:
                    audio_data = recognizer.listen(
                        source,
                        timeout=timeout,
                        phrase_time_limit=phrase_time_limit
                    )
                except sr.WaitTimeoutError:
                    if not self._stop_listening_flag.is_set():
                        self._set_state(VoiceState.IDLE)
                        self.error_occurred.emit("No speech detected within listening timeout. Please speak after pressing MIC.")
                    self.listening_finished.emit()
                    return

        except OSError as osc_err:
            logger.error(f"Microphone device access error: {osc_err}")
            self._set_state(VoiceState.ERROR)
            self.error_occurred.emit(f"Microphone hardware error: {osc_err}. Verify permissions in Windows Settings.")
            self.listening_finished.emit()
            return
        except Exception as exc:
            logger.error(f"Audio capture exception: {exc}")
            self._set_state(VoiceState.ERROR)
            self.error_occurred.emit(f"Audio capture failed: {exc}")
            self.listening_finished.emit()
            return

        if self._stop_listening_flag.is_set() or not audio_data:
            self._set_state(VoiceState.IDLE)
            self.listening_finished.emit()
            return

        # Check audio signal strength
        raw_bytes = audio_data.get_raw_data()
        rms = calculate_rms_level(raw_bytes)
        self.audio_level.emit(rms)

        # If audio energy was practically inaudible, avoid sending to cloud
        if rms < 0.003 and len(raw_bytes) < 8000:
            self._set_state(VoiceState.ERROR)
            self.error_occurred.emit("Audio signal was too faint or brief. Please speak closer to your microphone.")
            self.listening_finished.emit()
            return

        # Transition to processing state
        self._set_state(VoiceState.PROCESSING)
        self._transcribe_audio(recognizer, audio_data)

    def _transcribe_audio(self, recognizer, audio_data) -> None:
        """Transcribe captured audio using available speech recognizers."""
        text = ""
        transcription_error = ""

        # 1. Try offline Vosk if model exists
        if self._vosk_model_path:
            try:
                import vosk
                import wave
                import io

                wav_bytes = audio_data.get_wav_data(convert_rate=16000, convert_width=2)
                wf = wave.open(io.BytesIO(wav_bytes), "rb")
                model = vosk.Model(self._vosk_model_path)
                rec = vosk.KaldiRecognizer(model, wf.getframerate())
                rec.SetWords(True)

                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    rec.AcceptWaveform(data)

                res = json.loads(rec.FinalResult())
                text = res.get("text", "").strip()
            except Exception as v_err:
                logger.warning(f"Vosk offline recognition failed: {v_err}")

        # 2. Online Google STT fallback
        if not text:
            try:
                import speech_recognition as sr
                text = recognizer.recognize_google(audio_data, language=self.language)
            except sr.UnknownValueError:
                transcription_error = (
                    "Speech audio was detected, but no distinct words could be recognized. "
                    "Please speak clearly into your microphone, or use typed input."
                )
            except sr.RequestError as req_err:
                transcription_error = (
                    f"Speech recognition service network connection error: {req_err}. "
                    "Check your internet connection or use typed input."
                )
            except Exception as exc:
                transcription_error = f"Speech recognition exception: {exc}"

        # Emit results
        if text and text.strip():
            self._set_state(VoiceState.IDLE)
            self.transcription_ready.emit(text.strip())
        else:
            self._set_state(VoiceState.ERROR)
            self.error_occurred.emit(transcription_error or "Empty transcription. Please speak distinctly.")

        self.listening_finished.emit()

    def run_diagnostics(self) -> Dict[str, Any]:
        """Perform comprehensive microphone health check and audio diagnostics."""
        diag: Dict[str, Any] = {
            "microphone_available": False,
            "default_device": None,
            "device_count": 0,
            "sample_rate": None,
            "offline_model": bool(self._vosk_model_path),
            "status_message": "Unknown"
        }

        try:
            import pyaudio
            p = pyaudio.PyAudio()
            devices = self.get_input_devices()
            diag["device_count"] = len(devices)

            try:
                def_info = p.get_default_input_device_info()
                diag["default_device"] = def_info.get("name")
                diag["sample_rate"] = def_info.get("defaultSampleRate")
                diag["microphone_available"] = True
                diag["status_message"] = (
                    f"Microphone operational: '{def_info.get('name')}' "
                    f"(Rate: {def_info.get('defaultSampleRate')} Hz, Devices: {len(devices)})."
                )
            except Exception as d_err:
                diag["status_message"] = f"Microphone detection error: {d_err}"
            finally:
                p.terminate()

        except Exception as exc:
            diag["status_message"] = f"Audio driver initialization error: {exc}"

        return diag
