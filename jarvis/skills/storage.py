"""Persistent SQLite storage for Skill Forge workflows, steps, and execution history."""

import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from jarvis.config import DB_PATH
from jarvis.core.database import Database
from jarvis.skills.models import Skill, SkillStep, SkillExecutionResult, StepStatus


class SkillStorage:
    """Handles CRUD persistence for skills and execution records in the central SQLite DB."""

    def __init__(self, db: Optional[Database] = None, db_path: Optional[Path] = None):
        self.db = db or Database(db_path=db_path)
        self.db_path = str(db_path or self.db.db_path)
        self.init_skill_tables()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_skill_tables(self) -> None:
        """Create skills, skill_steps, and skill_executions tables."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS skills (
                        id TEXT PRIMARY KEY,
                        name TEXT UNIQUE NOT NULL,
                        description TEXT DEFAULT '',
                        enabled INTEGER DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS skill_steps (
                        id TEXT PRIMARY KEY,
                        skill_id TEXT NOT NULL,
                        step_order INTEGER NOT NULL,
                        action_type TEXT NOT NULL,
                        label TEXT DEFAULT '',
                        arguments TEXT NOT NULL,
                        require_confirmation INTEGER DEFAULT 0,
                        FOREIGN KEY(skill_id) REFERENCES skills(id) ON DELETE CASCADE
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS skill_executions (
                        id TEXT PRIMARY KEY,
                        skill_id TEXT NOT NULL,
                        skill_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        is_dry_run INTEGER DEFAULT 0,
                        started_at TEXT NOT NULL,
                        completed_at TEXT NOT NULL,
                        step_results TEXT NOT NULL,
                        error_message TEXT
                    )
                """)
        finally:
            conn.close()

        # Seed initial example skills if database has no skills
        self._seed_default_skills()

    def _seed_default_skills(self) -> None:
        """Provide out-of-the-box verified skills for immediate productivity."""
        if len(self.get_all_skills()) == 0:
            # 1. Start Coding Session
            coding_skill = Skill(
                name="Start Coding Session",
                description="Launch developer tools, open coding folder, and log preparation",
                enabled=True,
                steps=[
                    SkillStep(
                        action_type="log_message",
                        order=1,
                        label="Announce Session Initialization",
                        arguments={"message": "Initializing Coding Session protocols..."}
                    ),
                    SkillStep(
                        action_type="launch_app",
                        order=2,
                        label="Launch Text Editor",
                        arguments={"app_name": "Notepad"}
                    ),
                    SkillStep(
                        action_type="launch_app",
                        order=3,
                        label="Launch Terminal",
                        arguments={"app_name": "Command Prompt"}
                    ),
                    SkillStep(
                        action_type="system_diagnostics",
                        order=4,
                        label="Verify Host Hardware State",
                        arguments={}
                    ),
                ]
            )
            self.save_skill(coding_skill)

            # 2. Daily Health Check
            health_skill = Skill(
                name="System Health Check",
                description="Audit CPU, memory, uptime, and display diagnostic telemetry",
                enabled=True,
                steps=[
                    SkillStep(
                        action_type="log_message",
                        order=1,
                        label="Initiating Diagnostics",
                        arguments={"message": "Gathering hardware telemetry..."}
                    ),
                    SkillStep(
                        action_type="system_diagnostics",
                        order=2,
                        label="Query System Resources",
                        arguments={}
                    ),
                ]
            )
            self.save_skill(health_skill)

    def save_skill(self, skill: Skill) -> None:
        """Insert or update a skill and its ordered steps transactionally."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO skills (id, name, description, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        description = excluded.description,
                        enabled = excluded.enabled,
                        updated_at = excluded.updated_at
                """, (
                    skill.id,
                    skill.name,
                    skill.description,
                    1 if skill.enabled else 0,
                    skill.created_at,
                    skill.updated_at
                ))

                # Replace steps
                cursor.execute("DELETE FROM skill_steps WHERE skill_id = ?", (skill.id,))
                for step in skill.steps:
                    args_json = json.dumps(step.arguments)
                    cursor.execute("""
                        INSERT INTO skill_steps (
                            id, skill_id, step_order, action_type, label, arguments, require_confirmation
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        step.id,
                        skill.id,
                        step.order,
                        step.action_type,
                        step.label,
                        args_json,
                        1 if step.require_confirmation else 0
                    ))
        finally:
            conn.close()

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Load a single skill by ID with all steps ordered."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM skills WHERE id = ?", (skill_id,))
            skill_row = cursor.fetchone()
            if not skill_row:
                return None

            cursor.execute(
                "SELECT * FROM skill_steps WHERE skill_id = ? ORDER BY step_order ASC",
                (skill_id,)
            )
            step_rows = cursor.fetchall()
            steps = []
            for r in step_rows:
                args = json.loads(r["arguments"]) if r["arguments"] else {}
                step = SkillStep(
                    action_type=r["action_type"],
                    order=r["step_order"],
                    label=r["label"],
                    arguments=args,
                    require_confirmation=bool(r["require_confirmation"]),
                    id=r["id"]
                )
                steps.append(step)

            return Skill(
                id=skill_row["id"],
                name=skill_row["name"],
                description=skill_row["description"],
                enabled=bool(skill_row["enabled"]),
                steps=steps,
                created_at=skill_row["created_at"],
                updated_at=skill_row["updated_at"]
            )
        finally:
            conn.close()

    def get_skill_by_name(self, name: str) -> Optional[Skill]:
        """Find a skill by exact or case-insensitive name."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM skills WHERE LOWER(name) = LOWER(?)", (name.strip(),))
            row = cursor.fetchone()
            if row:
                return self.get_skill(row["id"])
            return None
        finally:
            conn.close()

    def get_all_skills(self) -> List[Skill]:
        """Retrieve all skills ordered by name."""
        conn = self.get_connection()
        skill_ids = []
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM skills ORDER BY name ASC")
            skill_ids = [row["id"] for row in cursor.fetchall()]
        finally:
            conn.close()

        skills = []
        for sid in skill_ids:
            s = self.get_skill(sid)
            if s:
                skills.append(s)
        return skills

    def delete_skill(self, skill_id: str) -> bool:
        """Delete skill and cascade delete steps."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
                return cursor.rowcount > 0
        finally:
            conn.close()

    def set_skill_enabled(self, skill_id: str, enabled: bool) -> bool:
        """Enable or disable a skill."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE skills SET enabled = ? WHERE id = ?",
                    (1 if enabled else 0, skill_id)
                )
                return cursor.rowcount > 0
        finally:
            conn.close()

    def duplicate_skill(self, skill_id: str, new_name: Optional[str] = None) -> Optional[Skill]:
        """Create a duplicate copy of a skill with a unique name."""
        original = self.get_skill(skill_id)
        if not original:
            return None

        dup_name = new_name or f"{original.name} (Copy)"
        # Ensure name uniqueness
        counter = 1
        candidate_name = dup_name
        while self.get_skill_by_name(candidate_name) is not None:
            candidate_name = f"{dup_name} {counter}"
            counter += 1

        new_steps = []
        for step in original.steps:
            new_step = SkillStep(
                action_type=step.action_type,
                order=step.order,
                label=step.label,
                arguments=dict(step.arguments),
                require_confirmation=step.require_confirmation
            )
            new_steps.append(new_step)

        new_skill = Skill(
            name=candidate_name,
            description=original.description,
            enabled=original.enabled,
            steps=new_steps
        )
        self.save_skill(new_skill)
        return new_skill

    def record_execution(self, result: SkillExecutionResult) -> None:
        """Save a completed workflow run result."""
        conn = self.get_connection()
        try:
            with conn:
                cursor = conn.cursor()
                step_results_json = json.dumps([r.to_dict() for r in result.step_results])
                cursor.execute("""
                    INSERT INTO skill_executions (
                        id, skill_id, skill_name, status, is_dry_run,
                        started_at, completed_at, step_results, error_message
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.execution_id,
                    result.skill_id,
                    result.skill_name,
                    result.status,
                    1 if result.is_dry_run else 0,
                    result.started_at,
                    result.completed_at,
                    step_results_json,
                    result.error_message
                ))
        finally:
            conn.close()
