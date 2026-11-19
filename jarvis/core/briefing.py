"""Executive Daily Briefing Protocol for O.M.E.N. / JARVIS.

Aggregates system telemetry, inbox intelligence, reminders, battery, and current status
into a cohesive morning/daily report suitable for HUD presentation and voice vocalization.
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional

from jarvis.core.database import Database
from jarvis.core.system_info import SystemInfoCollector
from jarvis.core.email_assistant import EmailAssistant


class BriefingManager:
    """Compiles tactical executive morning and status briefings."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
        self.email_assistant = EmailAssistant(self.db)

    def generate_briefing(self) -> Dict[str, Any]:
        """Generate a complete executive briefing."""
        now = datetime.now()
        hour = now.hour
        if hour < 12:
            greeting = "Good morning, Sir."
        elif hour < 17:
            greeting = "Good afternoon, Sir."
        else:
            greeting = "Good evening, Sir."

        date_str = now.strftime("%A, %B %d, %Y")
        time_str = now.strftime("%I:%M %p")

        # 1. Telemetry
        metrics = SystemInfoCollector.get_system_summary()
        cpu = metrics.get("cpu_percent", 0.0)
        ram = metrics.get("memory", {}).get("percent", 0.0)
        uptime = metrics.get("uptime", "N/A")

        # 2. Email Intelligence
        email_summary = self.email_assistant.check_unread_summary()
        unread_count = email_summary["count"]
        top_email = email_summary["emails"][0] if email_summary["emails"] else None

        # 3. Pending Reminders
        reminders = self.db.get_pending_reminders()
        reminder_count = len(reminders)

        # Build Formatted HUD Report
        lines = [
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"🛰 O.M.E.N. EXECUTIVE BRIEFING — {date_str.upper()}",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"{greeting} The current system time is {time_str}.",
            "",
            "📊 HARDWARE & TELEMETRY:",
            f" • CPU Utilization : {cpu}%",
            f" • Memory Usage    : {ram}%",
            f" • Host Uptime     : {uptime}",
            "",
            "✉️ INBOX INTELLIGENCE:",
        ]

        if unread_count > 0:
            lines.append(f" • {unread_count} Unread Message(s) awaiting review.")
            if top_email:
                lines.append(f" • Priority: From {top_email['sender']} — \"{top_email['subject']}\"")
        else:
            lines.append(" • Inbox clear. No unread messages.")

        lines.append("")
        lines.append("⏰ PENDING REMINDERS & TIMERS:")
        if reminder_count > 0:
            lines.append(f" • {reminder_count} Active Reminder(s) scheduled:")
            for r in reminders[:3]:
                due_dt = datetime.fromtimestamp(r["due_timestamp"]).strftime("%H:%M")
                lines.append(f"   - [{due_dt}] {r['message']}")
        else:
            lines.append(" • No active reminders.")

        lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # Vocal summary for Text-to-Speech
        spoken_parts = [
            f"{greeting} It is {time_str} on {date_str}.",
            f"Hardware diagnostics are green at {cpu} percent CPU and {ram} percent RAM."
        ]
        if unread_count > 0 and top_email:
            spoken_parts.append(f"You have {unread_count} unread emails, including an urgent dispatch from {top_email['sender']}.")
        else:
            spoken_parts.append("Your email inbox is currently clear.")

        if reminder_count > 0:
            spoken_parts.append(f"You have {reminder_count} scheduled reminders queued.")

        spoken_parts.append("All primary subsystems are nominal and standing by.")

        return {
            "success": True,
            "greeting": greeting,
            "timestamp": time_str,
            "date": date_str,
            "cpu_percent": cpu,
            "ram_percent": ram,
            "unread_emails": unread_count,
            "pending_reminders": reminder_count,
            "report_text": "\n".join(lines),
            "spoken_summary": " ".join(spoken_parts)
        }
