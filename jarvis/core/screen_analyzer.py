"""Multimodal screen capture and visual analysis module for O.M.E.N. using Gemini 2.5 Flash."""

import os
import io
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ScreenAnalyzer:
    """Safely captures user screen on demand and performs AI visual inspection using Gemini Vision."""

    @staticmethod
    def capture_primary_screen() -> Optional[bytes]:
        """Capture the user's primary display and return JPEG image bytes."""
        try:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtGui import QGuiApplication
            from PySide6.QtCore import QBuffer, QIODevice

            app = QApplication.instance()
            if not app:
                import sys
                app = QApplication(sys.argv)

            screen = QGuiApplication.primaryScreen()
            if not screen:
                logger.error("No primary display detected for screen capture.")
                return None

            pixmap = screen.grabWindow(0)
            if pixmap.isNull():
                logger.error("Screen capture resulted in null pixmap.")
                return None

            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            # Save as JPEG with 80% quality for optimal Gemini API payload size
            pixmap.save(buffer, "JPEG", 80)
            data = bytes(buffer.data())
            buffer.close()
            return data
        except Exception as e:
            logger.error(f"Error capturing primary screen: {e}")
            return None

    @classmethod
    def analyze_screen(cls, prompt: str = "Analyze the active screen and explain what is visible, highlighting any errors, open apps, or key details.", api_key: Optional[str] = None) -> Dict[str, Any]:
        """Capture the screen and submit to Google Gemini Multimodal Vision API."""
        img_bytes = cls.capture_primary_screen()
        if not img_bytes:
            return {
                "success": False,
                "message": "Screen capture failed. Ensure display output is accessible."
            }

        # Check API key
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
        if not key:
            try:
                from jarvis.core.database import Database
                key = Database().get_setting("gemini_api_key") or ""
            except Exception:
                pass

        if not key:
            return {
                "success": False,
                "message": "Gemini API key is required for screen vision analysis. Set GEMINI_API_KEY in your environment or settings."
            }

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=key.strip())
            part_img = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
            part_prompt = types.Part.from_text(text=prompt)

            model_name = os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
            resp = client.models.generate_content(
                model=model_name,
                contents=[types.Content(role="user", parts=[part_img, part_prompt])]
            )

            text = resp.text if getattr(resp, "text", None) else "Screen analyzed successfully."
            return {
                "success": True,
                "message": text,
                "size_bytes": len(img_bytes)
            }
        except Exception as exc:
            logger.error(f"Error during Gemini screen vision analysis: {exc}")
            return {
                "success": False,
                "message": f"Gemini Vision analysis error: {exc}"
            }
