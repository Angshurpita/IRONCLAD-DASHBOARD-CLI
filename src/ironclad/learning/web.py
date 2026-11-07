"""Embedded Web Server for the IRONCLAD Personalized Learning Dashboard.

Provides:
- User Authentication layer (Student vs Teacher role-based portals)
- REST API for curriculum graphs, student mastery, lesson synthesis, and teacher analytics
- Aligned to Class 10th Mathematics (NCERT / CBSE / ICSE / State Boards)
- Serves the interactive Web Application on localhost
"""

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from ironclad.config import IroncladSettings
from ironclad.learning.engine import PersonalizedLearningEngine
from ironclad.learning.graph import ConceptGraph, get_available_curricula
from ironclad.learning.models import (
    InterventionExplanation,
    LearningModality,
    StruggleType,
    TeacherAlert,
)
from ironclad.learning.storage import LearningStorage
from ironclad.learning.teacher import TeacherDashboardService

logger = logging.getLogger("ironclad.learning.web")

STATIC_DIR = Path(__file__).parent / "static"


class LearningDashboardHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler providing REST APIs, Auth layer, and serving UI assets."""

    server_settings: IroncladSettings
    storage: LearningStorage
    curricula: Dict[str, ConceptGraph]
    active_domain: str = "class10_maths"

    def log_message(self, format: str, *args: Any) -> None:
        """Quiet default server logging."""
        pass

    def do_HEAD(self) -> None:
        self.do_GET()

    def _get_auth_token(self) -> Optional[str]:
        auth_hdr = self.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            return auth_hdr[7:].strip()
        if "X-Auth-Token" in self.headers:
            return self.headers.get("X-Auth-Token", "").strip()
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        token_list = query.get("token")
        if token_list:
            return token_list[0].strip()
        return None

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)

        # 1. Auth Endpoints
        if path == "/api/auth/me":
            token = self._get_auth_token()
            if not token:
                self._send_json({"error": "No token provided"}, status=401)
                return
            user = self.storage.get_user_by_token(token)
            if not user:
                self._send_json({"error": "Session expired or invalid"}, status=401)
                return
            self._send_json({"user": user})
            return

        # 2. API Endpoints
        if path == "/api/curricula":
            data = [
                {
                    "domain": g.domain,
                    "title": g.title,
                    "concept_count": len(g.concepts),
                }
                for g in self.curricula.values()
            ]
            self._send_json(data)
            return

        if path == "/api/curriculum":
            domain = query.get("domain", [self.active_domain])[0]
            graph = self.curricula.get(domain) or list(self.curricula.values())[0]
            nodes = [c.model_dump() for c in graph.concepts.values()]
            self._send_json({
                "domain": graph.domain,
                "title": graph.title,
                "nodes": nodes,
            })
            return

        if path == "/api/class-summary":
            domain = query.get("domain", [self.active_domain])[0]
            graph = self.curricula.get(domain) or list(self.curricula.values())[0]
            service = TeacherDashboardService(self.storage, graph)
            summary = service.get_class_summary(domain)
            self._send_json(summary.model_dump())
            return

        if path == "/api/students":
            domain = query.get("domain", [self.active_domain])[0]
            students = self.storage.list_students(domain)
            self._send_json([s.model_dump() for s in students])
            return

        if path.startswith("/api/student/"):
            student_id = path.replace("/api/student/", "").strip()
            student = self.storage.get_student(student_id)
            if student:
                history = self.storage.get_assessment_history(student_id, limit=10)
                data = student.model_dump()
                data["recent_assessments"] = [h.model_dump() for h in history]
                self._send_json(data)
            else:
                self._send_json({"error": "Student not found"}, status=404)
            return

        if path.startswith("/api/explain/"):
            student_id = path.replace("/api/explain/", "").strip()
            cid = query.get("concept", [None])[0]
            domain = query.get("domain", [self.active_domain])[0]
            graph = self.curricula.get(domain) or list(self.curricula.values())[0]
            service = TeacherDashboardService(self.storage, graph)
            try:
                expl = service.explain_intervention(student_id, cid)
                self._send_json(expl.model_dump())
            except Exception as e:
                self._send_json({"error": str(e)}, status=400)
            return

        # 3. Static Asset & SPA Route Serving
        if path in ("", "/", "/teacher", "/student", "/login"):
            self._serve_file(STATIC_DIR / "index.html", "text/html")
        else:
            file_path = STATIC_DIR / path.lstrip("/")
            if file_path.exists() and file_path.is_file():
                content_type = "text/plain"
                if file_path.suffix == ".html":
                    content_type = "text/html"
                elif file_path.suffix == ".css":
                    content_type = "text/css"
                elif file_path.suffix == ".js":
                    content_type = "application/javascript"
                elif file_path.suffix == ".json":
                    content_type = "application/json"
                elif file_path.suffix == ".svg":
                    content_type = "image/svg+xml"
                self._serve_file(file_path, content_type)
            else:
                self._serve_file(STATIC_DIR / "index.html", "text/html")

    def do_POST(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        body = self._read_json_body()

        # Auth: Login
        if path == "/api/auth/login":
            username = body.get("username", "").strip()
            password = body.get("password", "").strip()
            role_hint = body.get("role", "")

            user = self.storage.authenticate_user(username, password)
            if not user:
                # Demo accounts shortcut
                uname_low = username.lower()
                if uname_low in ("teacher", "teacher@school.edu", "sunita", "hod"):
                    user = self.storage.authenticate_user("teacher@school.edu", "teacher123")
                elif uname_low in ("priya", "priya@school.edu", "s_priya"):
                    user = self.storage.authenticate_user("priya@school.edu", "student123")
                elif uname_low in ("aarav", "aarav@school.edu", "s_aarav"):
                    user = self.storage.authenticate_user("aarav@school.edu", "student123")
                elif uname_low in ("rohit", "rohit@school.edu", "s_rohit"):
                    user = self.storage.authenticate_user("rohit@school.edu", "student123")
                elif uname_low in ("ananya", "ananya@school.edu", "s_ananya"):
                    user = self.storage.authenticate_user("ananya@school.edu", "student123")

            if not user:
                self._send_json({"error": "Invalid username or password. Check credentials or use quick-demo."}, status=401)
                return

            if role_hint and user.get("role") != role_hint:
                self._send_json({"error": f"This account is registered as '{user.get('role')}', not '{role_hint}'."}, status=403)
                return

            token = self.storage.create_session(user["username"], user["role"])
            self._send_json({"token": token, "user": user})
            return

        # Auth: Demo quick switcher
        if path == "/api/auth/demo":
            role = body.get("role", "student")
            student_id = body.get("student_id", "s_priya")
            if role == "teacher":
                user = self.storage.authenticate_user("teacher@school.edu", "teacher123")
            else:
                user_map = {
                    "s_priya": "priya@school.edu",
                    "s_aarav": "aarav@school.edu",
                    "s_rohit": "rohit@school.edu",
                    "s_ananya": "ananya@school.edu",
                }
                target_user = user_map.get(student_id, "priya@school.edu")
                user = self.storage.authenticate_user(target_user, "student123")

            if user:
                token = self.storage.create_session(user["username"], user["role"])
                self._send_json({"token": token, "user": user})
            else:
                self._send_json({"error": "Demo user not found"}, status=500)
            return

        # Auth: Logout
        if path == "/api/auth/logout":
            token = self._get_auth_token() or body.get("token")
            if token:
                self.storage.delete_session(token)
            self._send_json({"ok": True})
            return

        # Student Agency: Modality Preference selection
        if path == "/api/student/preference":
            student_id = body.get("student_id")
            modality_str = body.get("modality")
            if student_id and modality_str:
                st = self.storage.get_student(student_id)
                if st:
                    try:
                        mod = LearningModality(modality_str)
                        st.preferred_modality = mod
                        # Elevate the selected modality weight
                        for k in st.modality_weights:
                            if k == mod.value:
                                st.modality_weights[k] = min(0.60, round(st.modality_weights[k] + 0.15, 2))
                            else:
                                st.modality_weights[k] = max(0.08, round(st.modality_weights[k] - 0.04, 2))
                        self.storage.save_student(st)
                        self._send_json({"ok": True, "student": st.model_dump()})
                        return
                    except Exception as e:
                        self._send_json({"error": str(e)}, status=400)
                        return
            self._send_json({"error": "Invalid student preference payload"}, status=400)
            return

        # Teacher: Resolve Alert
        if path == "/api/resolve-alert":
            alert_id = body.get("alert_id")
            if alert_id:
                self.storage.resolve_alert(alert_id)
            self._send_json({"ok": True})
            return

        # Lesson Generation
        if path == "/api/lesson":
            student_id = body.get("student_id", "s_priya")
            concept_id = body.get("concept_id")
            domain = body.get("domain", self.active_domain)
            modality_str = body.get("modality")

            graph = self.curricula.get(domain) or list(self.curricula.values())[0]
            engine = PersonalizedLearningEngine(self.server_settings, self.storage, graph)

            modality = LearningModality(modality_str) if modality_str else None
            try:
                plan = engine.create_lesson_plan(student_id, concept_id, requested_modality=modality)
                self._send_json(plan.model_dump())
            except Exception as e:
                self._send_json({"error": str(e)}, status=400)
            return

        # Socratic Assessment Evaluation
        if path == "/api/assess":
            student_id = body.get("student_id", "s_priya")
            concept_id = body.get("concept_id")
            item_id = body.get("item_id")
            student_answer = body.get("student_answer", "")
            domain = body.get("domain", self.active_domain)
            latency = float(body.get("latency_sec", 6.0))

            graph = self.curricula.get(domain) or list(self.curricula.values())[0]
            engine = PersonalizedLearningEngine(self.server_settings, self.storage, graph)

            try:
                result = engine.evaluate_submission(
                    student_id=student_id,
                    concept_id=concept_id,
                    item_id=item_id,
                    student_answer=student_answer,
                    latency_sec=latency,
                )
                self._send_json(result.model_dump())
            except Exception as e:
                self._send_json({"error": str(e)}, status=400)
            return

        self._send_json({"error": "Not Found"}, status=404)

    def _read_json_body(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            raw = self.rfile.read(content_length).decode("utf-8")
            try:
                return json.loads(raw)
            except Exception:
                return {}
        return {}

    def _send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def _serve_file(self, file_path: Path, content_type: str) -> None:
        if not file_path.exists():
            self.send_error(404, "File Not Found")
            return
        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def run_dashboard_server(
    settings: IroncladSettings,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> ThreadingHTTPServer:
    """Initializes and runs the web dashboard HTTP server with Class 10th Maths primary focus."""
    learning_db = settings.ironclad_path / "learning.db"
    storage = LearningStorage(learning_db)

    raw_curricula = get_available_curricula()
    curricula = {dom: ConceptGraph(curr) for dom, curr in raw_curricula.items()}

    # Always ensure default Class 10th accounts exist
    _seed_demo_classroom(storage)

    class CustomServer(ThreadingHTTPServer):
        pass

    # Inject dependencies into handler
    LearningDashboardHandler.server_settings = settings
    LearningDashboardHandler.storage = storage
    LearningDashboardHandler.curricula = curricula
    LearningDashboardHandler.active_domain = "class10_maths"

    server = CustomServer((host, port), LearningDashboardHandler)
    return server


def _seed_demo_classroom(storage: LearningStorage) -> None:
    """
    Seeds Class 10th Mathematics students and teacher accounts.
    Explicitly aligns with Section 14 (page 6) of the research paper:
    Priya Sharma exhibits struggle in Quadratic Equations (35%) because of
    an unresolved prerequisite gap in Polynomials (Zeros & Factorization at 42%).
    """
    school = "Delhi Public School & CBSE State Division (Class 10)"

    # 1. Accounts
    storage.create_user(
        username="teacher@school.edu",
        password_clear="teacher123",
        role="teacher",
        name="Dr. Sunita Sharma",
        school_name=school,
    )
    storage.create_user(
        username="priya@school.edu",
        password_clear="student123",
        role="student",
        name="Priya Sharma",
        student_id="s_priya",
        school_name=school,
    )
    storage.create_user(
        username="aarav@school.edu",
        password_clear="student123",
        role="student",
        name="Aarav Patel",
        student_id="s_aarav",
        school_name=school,
    )
    storage.create_user(
        username="rohit@school.edu",
        password_clear="student123",
        role="student",
        name="Rohit Verma",
        student_id="s_rohit",
        school_name=school,
    )
    storage.create_user(
        username="ananya@school.edu",
        password_clear="student123",
        role="student",
        name="Ananya Iyer",
        student_id="s_ananya",
        school_name=school,
    )

    # 2. Student Profiles
    s1 = storage.get_or_create_student("s_priya", "Priya Sharma", domain="class10_maths")
    s1.concept_mastery = {
        "c10_real_numbers": 0.88,
        "c10_polynomials": 0.42,  # Root-cause prerequisite deficit
        "c10_linear_equations": 0.72,
        "c10_quadratic_equations": 0.35,  # Active struggle
        "c10_arithmetic_progressions": 0.52,
        "c10_triangles": 0.65,
        "c10_coordinate_geometry": 0.70,
        "c10_trigonometry": 0.58,
        "c10_statistics": 0.82,
        "c10_probability": 0.85,
    }
    s1.active_struggle = StruggleType.KNOWLEDGE_GAP
    s1.streak_incorrect = 3
    s1.preferred_modality = LearningModality.WORKED_EXAMPLES
    storage.save_student(s1)

    s2 = storage.get_or_create_student("s_aarav", "Aarav Patel", domain="class10_maths")
    s2.concept_mastery = {
        "c10_real_numbers": 0.95,
        "c10_polynomials": 0.92,
        "c10_linear_equations": 0.88,
        "c10_quadratic_equations": 0.86,
        "c10_arithmetic_progressions": 0.84,
        "c10_triangles": 0.78,
        "c10_coordinate_geometry": 0.82,
        "c10_trigonometry": 0.85,
        "c10_applications_trig": 0.80,
        "c10_circles": 0.79,
        "c10_surface_areas": 0.75,
        "c10_statistics": 0.90,
        "c10_probability": 0.92,
    }
    s2.streak_correct = 4
    s2.preferred_modality = LearningModality.PRACTICE_QUESTIONS
    storage.save_student(s2)

    s3 = storage.get_or_create_student("s_rohit", "Rohit Verma", domain="class10_maths")
    s3.concept_mastery = {
        "c10_real_numbers": 0.82,
        "c10_polynomials": 0.76,
        "c10_linear_equations": 0.75,
        "c10_quadratic_equations": 0.70,
        "c10_triangles": 0.38,  # Geometric similarity misconception
        "c10_coordinate_geometry": 0.65,
        "c10_statistics": 0.80,
        "c10_probability": 0.78,
    }
    s3.active_struggle = StruggleType.KNOWLEDGE_GAP
    s3.streak_incorrect = 2
    s3.preferred_modality = LearningModality.VISUAL
    storage.save_student(s3)

    s4 = storage.get_or_create_student("s_ananya", "Ananya Iyer", domain="class10_maths")
    s4.concept_mastery = {
        "c10_real_numbers": 0.98,
        "c10_polynomials": 0.96,
        "c10_linear_equations": 0.94,
        "c10_quadratic_equations": 0.95,
        "c10_arithmetic_progressions": 0.92,
        "c10_triangles": 0.90,
        "c10_coordinate_geometry": 0.92,
        "c10_trigonometry": 0.96,
        "c10_applications_trig": 0.94,
        "c10_circles": 0.91,
        "c10_surface_areas": 0.88,
        "c10_statistics": 0.95,
        "c10_probability": 0.98,
    }
    s4.streak_correct = 7
    s4.preferred_modality = LearningModality.SIMULATION
    storage.save_student(s4)

    # 3. Explainable AI Diagnostic Alert for Priya Sharma
    expl_priya = InterventionExplanation(
        student_id="s_priya",
        student_name="Priya Sharma",
        target_concept="Quadratic Equations & Nature of Roots (c10_quadratic_equations)",
        struggle_type=StruggleType.KNOWLEDGE_GAP,
        recommended_action="15-minute 1-on-1 review on 'Polynomials: Zeros & Coefficients'",
        prerequisite_root_cause="Polynomials: Zeros & Coefficients (c10_polynomials)",
        evidence_points=[
            "Failed 3 consecutive items on solving ax² + bx + c = 0 by splitting the middle term.",
            "Prerequisite 'c10_polynomials' mastery is deficient at 42.0% (below 65% threshold).",
            "Student struggles with identifying factor pairs of ac that sum to b.",
            "Preferred modality: Worked Examples (demonstrates higher comprehension when shown annotated step-by-step solutions).",
        ],
        suggested_teaching_strategy=(
            "Review factoring quadratic trinomials x² + (a+b)x + ab before resuming quadratic formula derivations."
        ),
    )
    alert_priya = TeacherAlert(
        alert_id="alert-c10-priya-quadratics",
        student_id="s_priya",
        student_name="Priya Sharma",
        concept_id="c10_quadratic_equations",
        severity="high",
        struggle_type=StruggleType.KNOWLEDGE_GAP,
        message="Priya Sharma struggles with Quadratic Equations due to unmastered prerequisite: Polynomials Zeros & Factoring.",
        explanation=expl_priya,
    )
    storage.save_teacher_alert(alert_priya)

    # 4. Diagnostic Alert for Rohit Verma
    expl_rohit = InterventionExplanation(
        student_id="s_rohit",
        student_name="Rohit Verma",
        target_concept="Similar Triangles & Basic Proportionality Theorem (c10_triangles)",
        struggle_type=StruggleType.KNOWLEDGE_GAP,
        recommended_action="Visual comparison worksheet between SAS Congruence vs SAS Similarity",
        prerequisite_root_cause="Similar Triangles & Basic Proportionality Theorem (c10_triangles)",
        evidence_points=[
            "Assumed that equal corresponding angles require equal side lengths rather than proportional sides.",
            "Average latency on geometric proofs is 14.5s indicating conceptual hesitation.",
            "Preferred modality: Visual Proof (absorbs geometric properties significantly faster with color-coded side ratios).",
        ],
        suggested_teaching_strategy=(
            "Use dynamic geometric dilation visualization to show constant angle preservation alongside variable side scale factors."
        ),
    )
    alert_rohit = TeacherAlert(
        alert_id="alert-c10-rohit-triangles",
        student_id="s_rohit",
        student_name="Rohit Verma",
        concept_id="c10_triangles",
        severity="medium",
        struggle_type=StruggleType.KNOWLEDGE_GAP,
        message="Rohit Verma confuses SAS similarity criterion with congruence in Triangles.",
        explanation=expl_rohit,
    )
    storage.save_teacher_alert(alert_rohit)

