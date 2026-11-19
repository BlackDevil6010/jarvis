"""Quick Notes and Voice Scratchpad for O.M.E.N. / JARVIS.

Enables instant recording of voice memos, ideas, and directives directly to SQLite.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime

from jarvis.core.database import Database


class NotesManager:
    """Manages creation, retrieval, and deletion of quick notes and voice memos."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def add_note(self, content: str, title: str = "") -> Dict[str, Any]:
        """Record a new memo or note."""
        clean_text = content.strip()
        if not clean_text:
            return {"success": False, "message": "Note content cannot be empty."}

        nid = self.db.add_note(clean_text, title=title)
        return {
            "success": True,
            "message": f"MEMO RECORDED [#{nid}]: \"{clean_text}\"",
            "note_id": nid,
            "content": clean_text
        }

    def list_notes(self, limit: int = 10) -> Dict[str, Any]:
        """Return formatted list of recent notes."""
        notes = self.db.get_all_notes(limit=limit)
        if not notes:
            return {
                "success": True,
                "notes": [],
                "message": "No recorded notes or memos found in memory."
            }

        lines = [f"SCRATCHPAD — {len(notes)} RECORDED NOTE(S):"]
        for n in notes:
            dt = datetime.fromtimestamp(n.get("created_timestamp", 0)).strftime("%Y-%m-%d %H:%M")
            title = n.get("title") or "Note"
            lines.append(f" • [#{n['id']}] ({dt}) {title}: {n['content']}")

        return {
            "success": True,
            "notes": notes,
            "message": "\n".join(lines)
        }

    def delete_note(self, note_id: int) -> Dict[str, Any]:
        """Remove a note by ID."""
        ok = self.db.delete_note(note_id)
        if ok:
            return {"success": True, "message": f"Note #{note_id} successfully purged from database."}
        return {"success": False, "message": f"Note #{note_id} not found."}
