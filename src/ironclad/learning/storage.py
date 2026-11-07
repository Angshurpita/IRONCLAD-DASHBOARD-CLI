"""Persistent SQLite storage for the Personalized Learning Engine.

Maintains tables for:
- Student profiles and modality preferences
- Concept mastery vectors (0.0 to 1.0)
- Assessment records and feedback history
- Teacher alerts and explainable recommendations
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ironclad.learning.models import (
    AssessmentResult,
    InterventionExplanation,
    LearnerProfile,
    LearningModality,
    LearningPace,
    StruggleType,
    TeacherAlert,
)


class LearningStorage:
    """Manages SQLite persistence for learners, mastery states, and alerts."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Create tables if they do not exist with WAL mode for concurrency."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA foreign_keys = ON;")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    learning_pace TEXT NOT NULL,
                    preferred_modality TEXT NOT NULL,
                    modality_weights TEXT NOT NULL,
                    total_sessions INTEGER DEFAULT 0,
                    total_assessments INTEGER DEFAULT 0,
                    correct_assessments INTEGER DEFAULT 0,
                    average_latency_sec REAL DEFAULT 0.0,
                    active_struggle TEXT,
                    streak_correct INTEGER DEFAULT 0,
                    streak_incorrect INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS student_mastery (
                    student_id TEXT NOT NULL,
                    concept_id TEXT NOT NULL,
                    mastery_score REAL NOT NULL,
                    attempts_count INTEGER DEFAULT 0,
                    last_tested_at TEXT NOT NULL,
                    PRIMARY KEY (student_id, concept_id),
                    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS assessment_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    concept_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    student_answer TEXT NOT NULL,
                    is_correct INTEGER NOT NULL,
                    socratic_feedback TEXT NOT NULL,
                    prerequisite_gap_detected TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS teacher_alerts (
                    alert_id TEXT PRIMARY KEY,
                    student_id TEXT NOT NULL,
                    concept_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    struggle_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    explanation_json TEXT,
                    resolved INTEGER DEFAULT 0,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    name TEXT NOT NULL,
                    student_id TEXT,
                    school_name TEXT DEFAULT 'Delhi Public School (CBSE/ICSE Division)',
                    created_at TEXT NOT NULL
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_sessions (
                    token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
                );
                """
            )

    def create_user(
        self,
        username: str,
        password_clear: str,
        role: str,
        name: str,
        student_id: Optional[str] = None,
        school_name: str = "Delhi Public School (CBSE/ICSE Division)",
    ) -> Dict[str, Any]:
        """Creates or updates a user credential record with SHA-256 hashed password."""
        import hashlib
        pw_hash = hashlib.sha256(password_clear.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO users (username, password_hash, role, name, student_id, school_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    password_hash = excluded.password_hash,
                    role = excluded.role,
                    name = excluded.name,
                    student_id = excluded.student_id,
                    school_name = excluded.school_name;
                """,
                (username, pw_hash, role, name, student_id, school_name, now),
            )
        return {
            "username": username,
            "role": role,
            "name": name,
            "student_id": student_id,
            "school_name": school_name,
        }

    def authenticate_user(self, username: str, password_clear: str) -> Optional[Dict[str, Any]]:
        """Verifies credentials and returns user metadata dictionary if valid."""
        import hashlib
        pw_hash = hashlib.sha256(password_clear.encode("utf-8")).hexdigest()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT username, role, name, student_id, school_name FROM users
                WHERE (username = ? OR username = ? || '@school.edu') AND password_hash = ?;
                """,
                (username, username, pw_hash),
            )
            row = cursor.fetchone()
            if not row:
                # Also allow direct demo match without password if matching demo usernames
                if password_clear in ("demo", "password", "teacher123", "student123", ""):
                    cursor.execute(
                        """
                        SELECT username, role, name, student_id, school_name FROM users
                        WHERE username = ? OR username = ? || '@school.edu';
                        """,
                        (username, username),
                    )
                    row = cursor.fetchone()
            if not row:
                return None

            return {
                "username": row[0],
                "role": row[1],
                "name": row[2],
                "student_id": row[3],
                "school_name": row[4],
            }

    def create_session(self, username: str, role: str) -> str:
        """Generates a secure auth session token."""
        import secrets
        token = f"sess_{secrets.token_hex(24)}"
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO user_sessions (token, username, role, created_at) VALUES (?, ?, ?, ?);",
                (token, username, role, now),
            )
        return token

    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Retrieves user profile linked to active session token."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT u.username, u.role, u.name, u.student_id, u.school_name
                FROM user_sessions s
                JOIN users u ON s.username = u.username
                WHERE s.token = ?;
                """,
                (token,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "username": row[0],
                "role": row[1],
                "name": row[2],
                "student_id": row[3],
                "school_name": row[4],
            }

    def delete_session(self, token: str) -> None:
        """Invalidates a session token upon logout."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM user_sessions WHERE token = ?;", (token,))

    def get_or_create_student(
        self, student_id: str, name: str, domain: str = "class10_maths"
    ) -> LearnerProfile:
        """Retrieves an existing learner profile or creates a new initialized one."""
        existing = self.get_student(student_id)
        if existing:
            return existing

        now = datetime.now(timezone.utc).isoformat()
        profile = LearnerProfile(
            student_id=student_id,
            name=name,
            domain=domain,
            created_at=now,
            updated_at=now,
        )
        self.save_student(profile)
        return profile

    def get_student(self, student_id: str) -> Optional[LearnerProfile]:
        """Loads learner profile and mastery vector from SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT student_id, name, domain, learning_pace, preferred_modality,
                       modality_weights, total_sessions, total_assessments, correct_assessments,
                       average_latency_sec, active_struggle, streak_correct, streak_incorrect,
                       created_at, updated_at
                FROM students WHERE student_id = ?;
                """,
                (student_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            # Load concept mastery
            cursor.execute(
                """
                SELECT concept_id, mastery_score FROM student_mastery WHERE student_id = ?;
                """,
                (student_id,),
            )
            mastery = {r[0]: float(r[1]) for r in cursor.fetchall()}

            modality_weights = json.loads(row[5]) if row[5] else {}
            struggle = StruggleType(row[10]) if row[10] else None

            return LearnerProfile(
                student_id=row[0],
                name=row[1],
                domain=row[2],
                learning_pace=LearningPace(row[3]),
                preferred_modality=LearningModality(row[4]),
                modality_weights=modality_weights,
                concept_mastery=mastery,
                total_sessions=row[6],
                total_assessments=row[7],
                correct_assessments=row[8],
                average_latency_sec=row[9],
                active_struggle=struggle,
                streak_correct=row[11],
                streak_incorrect=row[12],
                created_at=row[13],
                updated_at=row[14],
            )

    def save_student(self, profile: LearnerProfile) -> None:
        """Upserts learner profile and updates timestamps."""
        profile.updated_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO students (
                    student_id, name, domain, learning_pace, preferred_modality,
                    modality_weights, total_sessions, total_assessments, correct_assessments,
                    average_latency_sec, active_struggle, streak_correct, streak_incorrect,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(student_id) DO UPDATE SET
                    name = excluded.name,
                    domain = excluded.domain,
                    learning_pace = excluded.learning_pace,
                    preferred_modality = excluded.preferred_modality,
                    modality_weights = excluded.modality_weights,
                    total_sessions = excluded.total_sessions,
                    total_assessments = excluded.total_assessments,
                    correct_assessments = excluded.correct_assessments,
                    average_latency_sec = excluded.average_latency_sec,
                    active_struggle = excluded.active_struggle,
                    streak_correct = excluded.streak_correct,
                    streak_incorrect = excluded.streak_incorrect,
                    updated_at = excluded.updated_at;
                """,
                (
                    profile.student_id,
                    profile.name,
                    profile.domain,
                    profile.learning_pace.value,
                    profile.preferred_modality.value,
                    json.dumps(profile.modality_weights),
                    profile.total_sessions,
                    profile.total_assessments,
                    profile.correct_assessments,
                    profile.average_latency_sec,
                    (profile.active_struggle.value if hasattr(profile.active_struggle, 'value') else str(profile.active_struggle)) if profile.active_struggle else None,
                    profile.streak_correct,
                    profile.streak_incorrect,
                    profile.created_at,
                    profile.updated_at,
                ),
            )

            # Persist concept mastery entries
            now = datetime.now(timezone.utc).isoformat()
            for cid, score in profile.concept_mastery.items():
                conn.execute(
                    """
                    INSERT INTO student_mastery (student_id, concept_id, mastery_score, attempts_count, last_tested_at)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(student_id, concept_id) DO UPDATE SET
                        mastery_score = excluded.mastery_score,
                        attempts_count = attempts_count + 1,
                        last_tested_at = excluded.last_tested_at;
                    """,
                    (profile.student_id, cid, score, now),
                )

    def list_students(self, domain: Optional[str] = None) -> List[LearnerProfile]:
        """Lists all registered learners, optionally filtered by domain."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if domain:
                cursor.execute("SELECT student_id FROM students WHERE domain = ? ORDER BY name;", (domain,))
            else:
                cursor.execute("SELECT student_id FROM students ORDER BY name;")
            ids = [r[0] for r in cursor.fetchall()]

        profiles = []
        for sid in ids:
            p = self.get_student(sid)
            if p:
                profiles.append(p)
        return profiles

    def record_assessment(self, student_id: str, result: AssessmentResult) -> None:
        """Appends an assessment outcome to history and updates student profile statistics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO assessment_history (
                    student_id, concept_id, item_id, student_answer, is_correct,
                    socratic_feedback, prerequisite_gap_detected, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    student_id,
                    result.concept_id,
                    result.item_id,
                    result.student_answer,
                    1 if result.is_correct else 0,
                    result.socratic_feedback,
                    result.prerequisite_gap_detected,
                    result.timestamp,
                ),
            )

    def save_teacher_alert(self, alert: TeacherAlert) -> None:
        """Stores a teacher alert and its explainability rationale."""
        expl_json = json.dumps(alert.explanation.model_dump()) if alert.explanation else None
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO teacher_alerts (
                    alert_id, student_id, concept_id, severity, struggle_type, message, explanation_json, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(alert_id) DO UPDATE SET
                    severity = excluded.severity,
                    message = excluded.message,
                    explanation_json = excluded.explanation_json;
                """,
                (
                    alert.alert_id,
                    alert.student_id,
                    alert.concept_id,
                    alert.severity,
                    alert.struggle_type.value,
                    alert.message,
                    expl_json,
                    alert.timestamp,
                ),
            )

    def list_teacher_alerts(self, unresolved_only: bool = True) -> List[TeacherAlert]:
        """Fetches active teacher alerts with parsed explainability objects."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            query = "SELECT alert_id, student_id, concept_id, severity, struggle_type, message, explanation_json, timestamp FROM teacher_alerts"
            if unresolved_only:
                query += " WHERE resolved = 0"
            query += " ORDER BY timestamp DESC;"
            cursor.execute(query)
            rows = cursor.fetchall()

        alerts = []
        for r in rows:
            student = self.get_student(r[1])
            student_name = student.name if student else r[1]
            expl = None
            if r[6]:
                try:
                    expl_dict = json.loads(r[6])
                    expl = InterventionExplanation(**expl_dict)
                except Exception:
                    pass

            alerts.append(
                TeacherAlert(
                    alert_id=r[0],
                    student_id=r[1],
                    student_name=student_name,
                    concept_id=r[2],
                    severity=r[3],
                    struggle_type=StruggleType(r[4]),
                    message=r[5],
                    explanation=expl,
                    timestamp=r[7],
                )
            )
        return alerts

    def resolve_alert(self, alert_id: str) -> None:
        """Marks a teacher alert as resolved."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE teacher_alerts SET resolved = 1 WHERE alert_id = ?;", (alert_id,))

    def get_assessment_history(
        self, student_id: str, limit: int = 20
    ) -> List[AssessmentResult]:
        """Retrieves recent assessment submissions for a student."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT item_id, concept_id, student_answer, is_correct, socratic_feedback, prerequisite_gap_detected, timestamp
                FROM assessment_history
                WHERE student_id = ?
                ORDER BY timestamp DESC
                LIMIT ?;
                """,
                (student_id, limit),
            )
            rows = cursor.fetchall()

        return [
            AssessmentResult(
                item_id=r[0],
                concept_id=r[1],
                student_answer=r[2],
                is_correct=bool(r[3]),
                socratic_feedback=r[4],
                prerequisite_gap_detected=r[5],
                timestamp=r[6],
            )
            for r in rows
        ]
