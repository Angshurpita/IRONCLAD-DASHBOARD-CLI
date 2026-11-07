"""Vercel Serverless Function entry point for IRONCLAD Personalized Learning Dashboard."""

import json
import logging
import os
import shutil
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ironclad.vercel")

# Ensure src directory is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ironclad.config import IroncladSettings
from ironclad.learning.graph import ConceptGraph, get_available_curricula
from ironclad.learning.storage import LearningStorage
from ironclad.learning.web import LearningDashboardHandler, _seed_demo_classroom

# In serverless environments (e.g. Vercel Lambda), only /tmp is writable.
TMP_DIR = Path("/tmp")
DB_PATH = TMP_DIR / "ironclad_learning.db"

# Seed SQLite database in /tmp if not already initialized
seed_db = ROOT_DIR / ".ironclad" / "learning.db"
if not DB_PATH.exists() and seed_db.exists():
    try:
        shutil.copy2(seed_db, DB_PATH)
    except Exception as e:
        logger.warning(f"Could not copy seed database: {e}")

# Initialize settings, storage, and curricula
settings = IroncladSettings(project_root=ROOT_DIR)
storage = LearningStorage(DB_PATH)
raw_curricula = get_available_curricula()
curricula = {dom: ConceptGraph(curr) for dom, curr in raw_curricula.items()}

# Seed default demo accounts (Dr. Sunita Sharma, Priya Sharma, etc.)
_seed_demo_classroom(storage)

# Configure the request handler class
LearningDashboardHandler.server_settings = settings
LearningDashboardHandler.storage = storage
LearningDashboardHandler.curricula = curricula
LearningDashboardHandler.active_domain = "class10_maths"


class handler(LearningDashboardHandler):
    """Vercel Serverless Function HTTP Handler."""

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_OPTIONS(self) -> None:
        """Handle CORS pre-flight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        # Health & info endpoint
        if path in ("/api", "/api/", "/api/health"):
            self._send_json({
                "status": "healthy",
                "service": "IRONCLAD Personalized Learning API",
                "version": "0.1.0",
                "environment": "vercel-serverless",
                "active_domain": self.active_domain,
            })
            return

        super().do_GET()

    def do_POST(self) -> None:
        super().do_POST()

