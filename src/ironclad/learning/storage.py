"""Persistent SQLite storage for the Personalized Learning Engine.

Maintains tables for:
- Student profiles and modality preferences
- Concept mastery vectors (0.0 to 1.0)
- Assessment records and feedback history
- Teacher alerts and explainable recommendations
"""

import json
import logging
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

logger = logging.getLogger("ironclad.learning.storage")

# In-memory user and session registry fallback for serverless cold-starts
_MEMORY_USERS: Dict[str, Dict[str, Any]] = {}
_MEMORY_SESSIONS: Dict[str, Dict[str, Any]] = {}



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
                    school_name TEXT DEFAULT 'IRONCLAD Academy',
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

        self._seed_default_data()

    def _seed_default_data(self) -> None:
        """Seeds default evaluation accounts, learners, and diagnostic alerts for immediate evaluation."""
        import hashlib
        demo_student_pw = hashlib.sha256(b"student123").hexdigest()
        demo_teacher_pw = hashlib.sha256(b"teacher123").hexdigest()
        now = datetime.now(timezone.utc).isoformat()

        # In-memory registry fallback for cold-starts
        _MEMORY_USERS["student@academy.edu"] = {
            "username": "student@academy.edu",
            "password_hash": demo_student_pw,
            "role": "student",
            "name": "Alex Student",
            "student_id": "s_student",
            "school_name": "IRONCLAD Academy",
            "created_at": now,
        }
        _MEMORY_USERS["educator@academy.edu"] = {
            "username": "educator@academy.edu",
            "password_hash": demo_teacher_pw,
            "role": "teacher",
            "name": "Academic Lead",
            "student_id": None,
            "school_name": "IRONCLAD Academy",
            "created_at": now,
        }

        try:
            with sqlite3.connect(self.db_path) as conn:
                # Seed default users
                conn.execute(
                    """
                    INSERT OR IGNORE INTO users (username, password_hash, role, name, student_id, school_name, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    ("student@academy.edu", demo_student_pw, "student", "Alex Student", "s_student", "IRONCLAD Academy", now),
                )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO users (username, password_hash, role, name, student_id, school_name, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    ("educator@academy.edu", demo_teacher_pw, "teacher", "Academic Lead", None, "IRONCLAD Academy", now),
                )

                # Check if students exist
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM students;")
                if cur.fetchone()[0] == 0:
                    default_students = [
                        (
                            "s_student", "Alex Student", "class10_maths", "standard", "worked_examples",
                            json.dumps({"worked_examples": 0.40, "socratic_dialogue": 0.25, "visual_diagrams": 0.20, "formal_proof": 0.15}),
                            14, 20, 16, 7.8, "upstream_prerequisite_gap", 4, 0, now, now
                        ),
                        (
                            "s_rohan", "Rohan Verma", "class10_maths", "thorough", "visual_diagrams",
                            json.dumps({"worked_examples": 0.20, "socratic_dialogue": 0.20, "visual_diagrams": 0.45, "formal_proof": 0.15}),
                            9, 15, 10, 11.2, "calculation_carelessness", 1, 1, now, now
                        ),
                        (
                            "s_priya", "Priya Sharma", "class10_maths", "fast", "socratic_dialogue",
                            json.dumps({"worked_examples": 0.15, "socratic_dialogue": 0.45, "visual_diagrams": 0.25, "formal_proof": 0.15}),
                            18, 26, 24, 5.4, None, 6, 0, now, now
                        ),
                    ]
                    conn.executemany(
                        """
                        INSERT INTO students (
                            student_id, name, domain, learning_pace, preferred_modality,
                            modality_weights, total_sessions, total_assessments, correct_assessments,
                            average_latency_sec, active_struggle, streak_correct, streak_incorrect,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        default_students,
                    )

                    masteries = [
                        ("s_student", "c10_real_numbers_euclid", 0.90, 4, now),
                        ("s_student", "c10_real_numbers_fundamental_arithmetic", 0.85, 3, now),
                        ("s_student", "c10_real_numbers_irrational", 0.72, 3, now),
                        ("s_student", "c10_polynomials_zeroes_geometry", 0.38, 5, now),
                        ("s_student", "c10_quadratic_equations_factorisation", 0.65, 2, now),
                        ("s_rohan", "c10_real_numbers_euclid", 0.70, 3, now),
                        ("s_rohan", "c10_linear_equations_graphical", 0.45, 4, now),
                        ("s_priya", "c10_real_numbers_euclid", 0.96, 5, now),
                        ("s_priya", "c10_polynomials_zeroes_geometry", 0.92, 4, now),
                        ("s_priya", "c10_triangles_similarity_criteria", 0.88, 3, now),
                    ]
                    conn.executemany(
                        """
                        INSERT INTO student_mastery (student_id, concept_id, mastery_score, attempts_count, last_tested_at)
                        VALUES (?, ?, ?, ?, ?);
                        """,
                        masteries,
                    )

                    expl_json = json.dumps({
                        "student_id": "s_student",
                        "student_name": "Alex Student",
                        "target_concept": "Geometrical Meaning of Zeroes of a Polynomial",
                        "concept_id": "c10_polynomials_zeroes_geometry",
                        "struggle_type": "upstream_prerequisite_gap",
                        "diagnosed_gap_concept": "Linear Equations Graphical Representation",
                        "explanation": "Alex exhibits repeated errors when interpreting parabola x-intercepts on the Cartesian plane. The diagnostic trace shows a prerequisite deficiency in mapping polynomial zeroes to coordinate intersections from earlier modules.",
                        "recommended_action": "Targeted remediation session focusing on graphical coordinate intercepts before continuing to higher degree polynomial zeroes.",
                        "confidence_score": 0.89,
                    })
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO teacher_alerts (
                            alert_id, student_id, concept_id, severity, struggle_type, message, explanation_json, resolved, timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?);
                        """,
                        (
                            "alert_s_student_poly",
                            "s_student",
                            "c10_polynomials_zeroes_geometry",
                            "high",
                            "upstream_prerequisite_gap",
                            "Persistent difficulty interpreting geometrical zeroes of polynomials. Upstream prerequisite deficiency detected.",
                            expl_json,
                            now,
                        ),
                    )
        except Exception as e:
            logger.warning(f"Seed default data warning: {e}")

    def create_user(
        self,
        username: str,
        password_clear: str,
        role: str,
        name: str,
        student_id: Optional[str] = None,
        school_name: str = "IRONCLAD Academy",
    ) -> Dict[str, Any]:
        """Creates or updates a user credential record with SHA-256 hashed password."""
        import hashlib
        pw_hash = hashlib.sha256(password_clear.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        u_obj = {
            "username": username.strip(),
            "role": role.strip(),
            "name": name.strip(),
            "student_id": student_id,
            "school_name": school_name.strip(),
        }

        # Store in memory registry for resilience across serverless cold-starts
        _MEMORY_USERS[username.strip().lower()] = {
            **u_obj,
            "password_hash": pw_hash,
            "created_at": now,
        }

        try:
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
                    (username.strip(), pw_hash, role.strip(), name.strip(), student_id, school_name.strip(), now),
                )
        except Exception as e:
            logger.warning(f"Could not persist user to SQLite: {e}")

        return u_obj

    def user_exists(self, username: str) -> bool:
        """Checks if a user already exists by username or email."""
        norm = username.strip().lower()
        if norm in _MEMORY_USERS:
            return True
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM users WHERE LOWER(username) = LOWER(?);", (username.strip(),))
                return cursor.fetchone() is not None
        except Exception:
            return False

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Retrieves user profile by username."""
        norm = username.strip().lower()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT username, role, name, student_id, school_name FROM users WHERE LOWER(username) = LOWER(?);",
                    (username.strip(),),
                )
                row = cursor.fetchone()
                if row:
                    return {
                        "username": row[0],
                        "role": row[1],
                        "name": row[2],
                        "student_id": row[3],
                        "school_name": row[4],
                    }
        except Exception:
            pass

        mem_user = _MEMORY_USERS.get(norm)
        if mem_user:
            return {
                "username": mem_user["username"],
                "role": mem_user["role"],
                "name": mem_user["name"],
                "student_id": mem_user["student_id"],
                "school_name": mem_user["school_name"],
            }
        return None

    def authenticate_user(self, username: str, password_clear: str) -> Optional[Dict[str, Any]]:
        """Verifies credentials securely against stored SHA-256 password hash."""
        import hashlib
        pw_hash = hashlib.sha256(password_clear.encode("utf-8")).hexdigest()
        norm = username.strip().lower()

        # 1. Try SQLite
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT username, role, name, student_id, school_name FROM users
                    WHERE LOWER(username) = LOWER(?) AND password_hash = ?;
                    """,
                    (username.strip(), pw_hash),
                )
                row = cursor.fetchone()
                if row:
                    return {
                        "username": row[0],
                        "role": row[1],
                        "name": row[2],
                        "student_id": row[3],
                        "school_name": row[4],
                    }
        except Exception as e:
            logger.warning(f"Database query error in authenticate_user: {e}")

        # 2. Try Memory Cache
        mem_user = _MEMORY_USERS.get(norm)
        if mem_user and mem_user.get("password_hash") == pw_hash:
            # Re-seed into SQLite if connection is alive
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO users (username, password_hash, role, name, student_id, school_name, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            mem_user["username"],
                            mem_user["password_hash"],
                            mem_user["role"],
                            mem_user["name"],
                            mem_user["student_id"],
                            mem_user["school_name"],
                            mem_user.get("created_at", datetime.now(timezone.utc).isoformat()),
                        ),
                    )
            except Exception:
                pass
            return {
                "username": mem_user["username"],
                "role": mem_user["role"],
                "name": mem_user["name"],
                "student_id": mem_user["student_id"],
                "school_name": mem_user["school_name"],
            }

        return None

    def create_session(self, username: str, role: str) -> str:
        """Generates a secure HMAC-SHA256 signed session token and persists it."""
        import base64
        import hashlib
        import hmac
        import time

        now = datetime.now(timezone.utc).isoformat()
        user = self.get_user(username)
        name = user.get("name", username) if user else username
        student_id = user.get("student_id") if user else None
        school_name = user.get("school_name", "IRONCLAD Academy") if user else "IRONCLAD Academy"

        payload = json.dumps({
            "sub": username,
            "role": role,
            "name": name,
            "student_id": student_id,
            "school_name": school_name,
            "iat": int(time.time()),
            "exp": int(time.time()) + (7 * 86400),
        }, separators=(",", ":")).encode("utf-8")
        b64_payload = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
        sig = hmac.new(b"ironclad_educational_auth_salt_v1", payload, hashlib.sha256).hexdigest()[:32]
        token = f"sess_{b64_payload}_{sig}"

        _MEMORY_SESSIONS[token] = {
            "token": token,
            "username": username,
            "role": role,
            "name": name,
            "student_id": student_id,
            "school_name": school_name,
            "created_at": now,
        }

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO user_sessions (token, username, role, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(token) DO UPDATE SET created_at = excluded.created_at;
                    """,
                    (token, username, role, now),
                )
        except Exception as e:
            logger.warning(f"Could not persist session to SQLite: {e}")

        return token

    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Retrieves user profile linked to session token with resilient fallback."""
        if not token:
            return None

        # 1. Try SQLite
        try:
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
                if row:
                    return {
                        "username": row[0],
                        "role": row[1],
                        "name": row[2],
                        "student_id": row[3],
                        "school_name": row[4],
                    }
        except Exception:
            pass

        # 2. Try in-memory sessions cache
        if token in _MEMORY_SESSIONS:
            sess = _MEMORY_SESSIONS[token]
            return {
                "username": sess["username"],
                "role": sess["role"],
                "name": sess["name"],
                "student_id": sess["student_id"],
                "school_name": sess["school_name"],
            }

        # 3. Stateless cryptographic HMAC verification (survives container recycling)
        if token.startswith("sess_") and "_" in token[5:]:
            import base64
            import hashlib
            import hmac
            import time
            try:
                parts = token[5:].split("_")
                if len(parts) >= 2:
                    b64_payload = parts[0]
                    provided_sig = parts[1]
                    padding = 4 - (len(b64_payload) % 4)
                    if padding < 4:
                        b64_payload += "=" * padding
                    payload_bytes = base64.urlsafe_b64decode(b64_payload)
                    expected_sig = hmac.new(b"ironclad_educational_auth_salt_v1", payload_bytes, hashlib.sha256).hexdigest()[:32]
                    if hmac.compare_digest(provided_sig, expected_sig):
                        data = json.loads(payload_bytes.decode("utf-8"))
                        if data.get("exp", 0) > time.time():
                            username = data.get("sub", "")
                            role = data.get("role", "student")
                            name = data.get("name") or username.split("@")[0].capitalize()
                            student_id = data.get("student_id") or (f"s_{username.replace('@', '_').replace('.', '_')}" if role == "student" else None)
                            school_name = data.get("school_name", "IRONCLAD Academy")

                            user_obj = {
                                "username": username,
                                "role": role,
                                "name": name,
                                "student_id": student_id,
                                "school_name": school_name,
                            }
                            # Cache in memory
                            _MEMORY_SESSIONS[token] = {**user_obj, "token": token, "created_at": datetime.now(timezone.utc).isoformat()}
                            _MEMORY_USERS[username.lower()] = {**user_obj, "password_hash": ""}
                            return user_obj
            except Exception as e:
                logger.warning(f"HMAC token decode error: {e}")

        return None

    def delete_session(self, token: str) -> None:
        """Invalidates a session token upon logout."""
        _MEMORY_SESSIONS.pop(token, None)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM user_sessions WHERE token = ?;", (token,))
        except Exception:
            pass

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
