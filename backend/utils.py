"""
DataSentinel — Shared Utilities
Session management, structured logging, and path helpers.
"""

import os
import re
import logging
import time
import shutil

# --- STRUCTURED LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("datasentinel")

# --- BACKEND ROOT ---
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# --- UUID VALIDATION ---
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def validate_session_id(session_id: str) -> str:
    """Validate that a session ID is a well-formed UUID to prevent path traversal."""
    if not _UUID_RE.match(session_id):
        raise ValueError(f"Invalid session ID format: {session_id}")
    return session_id


def _session_dir(session_id: str) -> str:
    """Resolve session directory relative to the backend root. Creates it if needed."""
    validate_session_id(session_id)
    path = os.path.join(_BACKEND_DIR, "sessions", session_id)
    os.makedirs(path, exist_ok=True)
    return path


def cleanup_stale_sessions(max_age_hours: float = 24) -> int:
    """Remove session directories older than max_age_hours. Returns count removed."""
    sessions_root = os.path.join(_BACKEND_DIR, "sessions")
    if not os.path.exists(sessions_root):
        return 0

    now = time.time()
    removed = 0
    for session_name in os.listdir(sessions_root):
        session_path = os.path.join(sessions_root, session_name)
        if os.path.isdir(session_path):
            age_hours = (now - os.path.getmtime(session_path)) / 3600
            if age_hours > max_age_hours:
                shutil.rmtree(session_path, ignore_errors=True)
                removed += 1
                logger.info(
                    "Cleaned up stale session: %s (age: %.1fh)", session_name, age_hours
                )
    return removed
