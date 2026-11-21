"""Catch-all Serverless Function handler for Vercel dynamic API routes."""

import sys
from pathlib import Path

# Ensure src and root directories are on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.index import handler
