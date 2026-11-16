"""Timers and Reminders subsystem for O.M.E.N. with persistent SQLite storage and OS alerts."""

import time
import logging
import threading
from typing import Dict, List, Any, Optional, Callable
from jarvis.core.database import Database

logger = logging.getLogger(__name__)


class ReminderManager:
    """Manages active timers and scheduled reminders with background tracking and notifications."""

    def __init__(self, db: Optional[Database] = None, on_trigger: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.db = db or Database()
        self.on_trigger = on_trigger
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the background reminder monitoring thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="ReminderMonitorThread")
            self._thread.start()
            logger.info("ReminderManager background monitor thread started.")

    def stop(self) -> None:
        """Stop background reminder monitor."""
        with self._lock:
            self._running = False

    def add_timer(self, minutes: float, label: str = "Timer") -> Dict[str, Any]:
        """Schedule a timer in minutes from now."""
        seconds = max(1.0, float(minutes) * 60.0)
        due = time.time() + seconds
        rem_id = self.db.add_reminder(message=label, due_timestamp=due)
        return {
            "id": rem_id,
            "label": label,
            "minutes": minutes,
            "seconds": seconds,
            "due_timestamp": due,
        }

    def add_reminder(self, label: str, delay_seconds: float) -> Dict[str, Any]:
        """Schedule a reminder with a delay in seconds."""
        due = time.time() + max(1.0, float(delay_seconds))
        rem_id = self.db.add_reminder(message=label, due_timestamp=due)
        return {
            "id": rem_id,
            "label": label,
            "delay_seconds": delay_seconds,
            "due_timestamp": due,
        }

    def list_pending(self) -> List[Dict[str, Any]]:
        """Return all upcoming reminders/timers with remaining time."""
        now = time.time()
        pending = self.db.get_pending_reminders()
        result = []
        for r in pending:
            remaining = max(0.0, r["due_timestamp"] - now)
            result.append({
                "id": r["id"],
                "message": r["message"],
                "remaining_seconds": round(remaining, 1),
                "remaining_minutes": round(remaining / 60.0, 1),
                "due_timestamp": r["due_timestamp"]
            })
        return result

    def _monitor_loop(self) -> None:
        """Continuously check for due reminders."""
        while self._running:
            try:
                now = time.time()
                pending = self.db.get_pending_reminders()
                for r in pending:
                    if r["due_timestamp"] <= now:
                        self.db.mark_reminder_completed(r["id"])
                        logger.info(f"Triggering reminder #{r['id']}: {r['message']}")
                        if self.on_trigger:
                            try:
                                self.on_trigger(r)
                            except Exception as ex:
                                logger.error(f"Error in reminder callback: {ex}")
            except Exception as e:
                logger.error(f"Error in ReminderManager loop: {e}")
            time.sleep(1.0)
