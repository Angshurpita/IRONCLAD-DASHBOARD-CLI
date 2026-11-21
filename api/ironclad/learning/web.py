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

    _server_settings_val: Any = None
    _storage_val: Any = None
    _curricula_val: Any = None
    active_domain: str = "class10_maths"

    @property
    def storage(self) -> Any:
        if self._storage_val is None:
            if getattr(self.__class__, "_storage_val", None) is not None:
                return self.__class__._storage_val
            from ironclad.learning.storage import LearningStorage
            db_path = Path("/tmp/ironclad_learning.db")
            self.__class__._storage_val = LearningStorage(db_path)
        return self.__class__._storage_val

    @storage.setter
    def storage(self, value: Any) -> None:
        self.__class__._storage_val = value

    @property
    def curricula(self) -> Dict[str, Any]:
        if self._curricula_val is None:
            if getattr(self.__class__, "_curricula_val", None) is not None:
                return self.__class__._curricula_val
            try:
                from ironclad.learning.graph import ConceptGraph, get_available_curricula
                raw = get_available_curricula()
                self.__class__._curricula_val = {dom: ConceptGraph(curr) for dom, curr in raw.items()}
            except Exception:
                self.__class__._curricula_val = {}
        return self.__class__._curricula_val

    @curricula.setter
    def curricula(self, value: Any) -> None:
        self.__class__._curricula_val = value

    @property
    def server_settings(self) -> Any:
        if self._server_settings_val is None:
            if getattr(self.__class__, "_server_settings_val", None) is not None:
                return self.__class__._server_settings_val
            try:
                from ironclad.config import IroncladSettings
                root = Path(__file__).resolve().parent.parent.parent.parent
                self.__class__._server_settings_val = IroncladSettings(project_root=root)
            except Exception:
                self.__class__._server_settings_val = None
        return self.__class__._server_settings_val

    @server_settings.setter
    def server_settings(self, value: Any) -> None:
        self.__class__._server_settings_val = value

    def log_message(self, format: str, *args: Any) -> None:
        """Quiet default server logging."""
        pass

    def do_HEAD(self) -> None:
        self.do_GET()

    def _get_effective_path(self) -> str:
        """Resolves request path normalizing across local execution and Vercel serverless rewrites."""
        # 1. Check HTTP proxy / edge headers first (most accurate representation of client's request)
        for hdr in ("x-forwarded-uri", "x-real-path", "x-matched-path", "x-vercel-matched-path"):
            val = self.headers.get(hdr)
            if val:
                p = urlparse(val).path
                if p and p not in ("/api", "/api/", "/api/index", "/api/index.py", "/api/[...path]"):
                    return p

        # 2. Rewritten path query param (from vercel.json: /api/index?path=/api/...)
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if "path" in query and query["path"]:
            p = query["path"][0]
            if p and p not in ("/api/index", "/api/index.py"):
                return urlparse(p).path

        # 3. Default to self.path
        return parsed.path

    def _get_effective_query(self) -> Dict[str, list[str]]:
        """Extracts and merges query parameters from self.path and forwarded proxy URIs."""
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        # Merge if rewritten path contained query string
        if "path" in query and query["path"]:
            p = query["path"][0]
            if "?" in p:
                nested = parse_qs(urlparse(p).query)
                for k, v in nested.items():
                    if k not in query:
                        query[k] = v

        # Check forwarded headers
        for hdr in ("x-forwarded-uri", "x-real-path"):
            val = self.headers.get(hdr)
            if val and "?" in val:
                fquery = parse_qs(urlparse(val).query)
                for k, v in fquery.items():
                    if k not in query:
                        query[k] = v

        return query

    def _get_auth_token(self) -> Optional[str]:
        """Extracts auth token supporting HTTP/1.1, HTTP/2 lowercasing, and custom headers."""
        auth_hdr = self.headers.get("Authorization") or self.headers.get("authorization") or ""
        if auth_hdr.startswith("Bearer "):
            return auth_hdr[7:].strip()
        x_token = self.headers.get("X-Auth-Token") or self.headers.get("x-auth-token") or ""
        if x_token:
            return x_token.strip()
        query = self._get_effective_query()
        token_list = query.get("token")
        if token_list:
            return token_list[0].strip()
        return None

    def do_GET(self) -> None:
        try:
            self._handle_get()
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"Error in do_GET: {tb}")
            self._send_json({"error": f"Server processing error: {str(e)}", "detail": tb[-400:]}, status=500)

    def _handle_get(self) -> None:
        path = self._get_effective_path()
        query = self._get_effective_query()

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
        try:
            self._handle_post()
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"Error in do_POST: {tb}")
            self._send_json({"error": f"Server processing error: {str(e)}", "detail": tb[-400:]}, status=500)

    def _handle_post(self) -> None:
        path = self._get_effective_path()
        body = self._read_json_body()

        # Auth: Register
        if path == "/api/auth/register":
            username = body.get("username", "").strip()
            password = body.get("password", "").strip()
            name = body.get("name", "").strip()
            role = body.get("role", "student").strip().lower()
            school_name = body.get("school_name", "").strip() or "IRONCLAD Academy"

            if not username or len(username) < 3:
                self._send_json({"error": "Username or email must be at least 3 characters."}, status=400)
                return
            if not password or len(password) < 4:
                self._send_json({"error": "Password must be at least 4 characters."}, status=400)
                return
            if not name:
                name = username.split("@")[0].replace(".", " ").title()
            if role not in ("student", "teacher"):
                role = "student"

            if self.storage.user_exists(username):
                self._send_json({"error": "An account with this username or email already exists."}, status=409)
                return

            student_id = f"s_{username.replace('@', '_').replace('.', '_')}" if role == "student" else None
            user = self.storage.create_user(
                username=username,
                password_clear=password,
                role=role,
                name=name,
                student_id=student_id,
                school_name=school_name,
            )

            if role == "student" and student_id:
                self.storage.get_or_create_student(student_id=student_id, name=name, domain=self.active_domain)

            token = self.storage.create_session(user["username"], user["role"])
            self._send_json({"token": token, "user": user, "message": "Account created successfully."}, status=201)
            return

        # Auth: Login
        if path == "/api/auth/login":
            username = body.get("username", "").strip()
            password = body.get("password", "").strip()
            role_hint = body.get("role", "").strip().lower()

            if not username or not password:
                self._send_json({"error": "Please provide both username and password."}, status=400)
                return

            user = self.storage.authenticate_user(username, password)
            if not user:
                self._send_json({"error": "Invalid credentials. Please verify your username and password."}, status=401)
                return

            if role_hint and user.get("role") != role_hint:
                self._send_json({"error": f"This account is registered as '{user.get('role')}', not '{role_hint}'."}, status=403)
                return

            token = self.storage.create_session(user["username"], user["role"])
            self._send_json({"token": token, "user": user})
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
            token = self._get_auth_token()
            user = self.storage.get_user_by_token(token) if token else None
            student_id = body.get("student_id") or (user.get("student_id") if user else None) or "student_active"
            concept_id = body.get("concept_id")
            domain = body.get("domain", self.active_domain)
            modality_str = body.get("modality")

            st_name = user.get("name", "Student") if user else "Student"
            self.storage.get_or_create_student(student_id, st_name, domain)

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
            token = self._get_auth_token()
            user = self.storage.get_user_by_token(token) if token else None
            student_id = body.get("student_id") or (user.get("student_id") if user else None) or "student_active"
            concept_id = body.get("concept_id")
            item_id = body.get("item_id")
            student_answer = body.get("student_answer", "")
            domain = body.get("domain", self.active_domain)
            latency = float(body.get("latency_sec", 6.0))

            st_name = user.get("name", "Student") if user else "Student"
            self.storage.get_or_create_student(student_id, st_name, domain)

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
        cl_hdr = self.headers.get("Content-Length") or self.headers.get("content-length") or "0"
        try:
            content_length = int(cl_hdr)
        except (ValueError, TypeError):
            content_length = 0
        if content_length > 0:
            try:
                raw = self.rfile.read(content_length).decode("utf-8")
                return json.loads(raw)
            except Exception as e:
                logger.warning(f"Error parsing JSON request body: {e}")
                return {}
        return {}

    def _send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, authorization, X-Auth-Token, x-auth-token, x-forwarded-uri")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, authorization, X-Auth-Token, x-auth-token, x-forwarded-uri")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
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

    class CustomServer(ThreadingHTTPServer):
        pass

    # Inject dependencies into handler
    LearningDashboardHandler.server_settings = settings
    LearningDashboardHandler.storage = storage
    LearningDashboardHandler.curricula = curricula
    LearningDashboardHandler.active_domain = "class10_maths"

    server = CustomServer((host, port), LearningDashboardHandler)
    return server


