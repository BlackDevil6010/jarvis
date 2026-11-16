"""SQLite database storage for JARVIS application shortcuts and settings."""

import sqlite3
import json
from typing import List, Dict, Optional, Any
from pathlib import Path
from jarvis.config import DB_PATH

DEFAULT_APPLICATIONS = [
    {
        "name": "Notepad",
        "aliases": ["notepad", "notes", "text editor"],
        "path": "notepad.exe",
        "args": "",
        "is_builtin": True,
        "description": "Windows standard plain text editor"
    },
    {
        "name": "Calculator",
        "aliases": ["calculator", "calc", "math"],
        "path": "calc.exe",
        "args": "",
        "is_builtin": True,
        "description": "Windows Calculator application"
    },
    {
        "name": "File Explorer",
        "aliases": ["explorer", "file explorer", "files", "my computer"],
        "path": "explorer.exe",
        "args": "",
        "is_builtin": True,
        "description": "Windows File Explorer"
    },
    {
        "name": "Task Manager",
        "aliases": ["task manager", "taskmgr", "tasks"],
        "path": "taskmgr.exe",
        "args": "",
        "is_builtin": True,
        "description": "Windows Task Manager"
    },
    {
        "name": "Paint",
        "aliases": ["paint", "mspaint", "draw"],
        "path": "mspaint.exe",
        "args": "",
        "is_builtin": True,
        "description": "Windows Paint graphics utility"
    },
    {
        "name": "Command Prompt",
        "aliases": ["cmd", "command prompt", "terminal"],
        "path": "cmd.exe",
        "args": "",
        "is_builtin": True,
        "description": "Windows Command Prompt console"
    },
    {
        "name": "Google Chrome",
        "aliases": ["chrome", "google chrome", "browser"],
        "path": "chrome.exe",
        "args": "",
        "is_builtin": True,
        "description": "Google Chrome Web Browser"
    },
    {
        "name": "Visual Studio Code",
        "aliases": ["vscode", "vs code", "code"],
        "path": "code.exe",
        "args": "",
        "is_builtin": True,
        "description": "Visual Studio Code Editor"
    },
    {
        "name": "Microsoft Edge",
        "aliases": ["edge", "microsoft edge", "msedge"],
        "path": "msedge.exe",
        "args": "",
        "is_builtin": True,
        "description": "Microsoft Edge Web Browser"
    }
]


class Database:
    """Manages SQLite persistence for apps, settings, and logs."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or DB_PATH)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Create tables if they do not exist and seed default applications."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS applications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        aliases TEXT NOT NULL,
                        path TEXT NOT NULL,
                        args TEXT DEFAULT '',
                        is_builtin INTEGER DEFAULT 0,
                        description TEXT DEFAULT ''
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS command_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        command TEXT NOT NULL,
                        status TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS reminders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message TEXT NOT NULL,
                        due_timestamp REAL NOT NULL,
                        created_timestamp REAL NOT NULL,
                        status TEXT DEFAULT 'pending'
                    )
                """)
        finally:
            conn.close()

        # Seed defaults if applications table is missing any
        self._seed_default_apps()

    def _seed_default_apps(self) -> None:
        """Populate default applications if not already registered."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                for app in DEFAULT_APPLICATIONS:
                    aliases_str = json.dumps(app["aliases"])
                    cursor.execute("""
                        INSERT OR IGNORE INTO applications (name, aliases, path, args, is_builtin, description)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        app["name"],
                        aliases_str,
                        app["path"],
                        app["args"],
                        1 if app["is_builtin"] else 0,
                        app["description"]
                    ))
        finally:
            conn.close()

    def get_all_applications(self) -> List[Dict[str, Any]]:
        """Retrieve all registered applications."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM applications ORDER BY name ASC")
            rows = cursor.fetchall()
            results = []
            for row in rows:
                aliases = json.loads(row["aliases"]) if row["aliases"] else []
                results.append({
                    "id": row["id"],
                    "name": row["name"],
                    "aliases": aliases,
                    "path": row["path"],
                    "args": row["args"],
                    "is_builtin": bool(row["is_builtin"]),
                    "description": row["description"]
                })
            return results
        finally:
            conn.close()

    def get_application_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find an application by exact name or match against aliases."""
        clean_query = name.strip().lower()
        apps = self.get_all_applications()
        for app in apps:
            if app["name"].lower() == clean_query:
                return app
            for alias in app["aliases"]:
                if alias.lower() == clean_query:
                    return app
        return None

    def add_or_update_application(
        self,
        name: str,
        path: str,
        aliases: List[str],
        args: str = "",
        description: str = "",
        is_builtin: bool = False
    ) -> bool:
        """Register a new application or update an existing one."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                aliases_str = json.dumps(aliases)
                cursor.execute("""
                    INSERT INTO applications (name, aliases, path, args, is_builtin, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        aliases=excluded.aliases,
                        path=excluded.path,
                        args=excluded.args,
                        description=excluded.description
                """, (name, aliases_str, path, args, 1 if is_builtin else 0, description))
                return True
        finally:
            conn.close()

    def delete_application(self, name: str) -> bool:
        """Delete an application shortcut from registry."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM applications WHERE name = ?", (name,))
                return cursor.rowcount > 0
        finally:
            conn.close()

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve a persistent setting by key."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default
        finally:
            conn.close()

    def set_setting(self, key: str, value: str) -> None:
        """Store or update a persistent setting."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO settings (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """, (key, str(value)))
        finally:
            conn.close()

    def record_command(self, command: str, status: str) -> None:
        """Save a executed command to history."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO command_history (command, status)
                    VALUES (?, ?)
                """, (command, status))
        finally:
            conn.close()

    def add_reminder(self, message: str, due_timestamp: float) -> int:
        """Store a new timer/reminder in the database."""
        import time
        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO reminders (message, due_timestamp, created_timestamp, status)
                    VALUES (?, ?, ?, 'pending')
                """, (message, due_timestamp, time.time()))
                return cursor.lastrowid
        finally:
            conn.close()

    def get_pending_reminders(self) -> List[Dict[str, Any]]:
        """Retrieve all currently active / pending reminders."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reminders WHERE status = 'pending' ORDER BY due_timestamp ASC")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def mark_reminder_completed(self, reminder_id: int) -> None:
        """Mark a completed reminder."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE reminders SET status = 'completed' WHERE id = ?", (reminder_id,))
        finally:
            conn.close()
