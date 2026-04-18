"""
Session management for contao-cli-agent.
Stores SSH connection config and provides session file locking.
"""
import json
import os
import sys
from pathlib import Path

# fcntl is Unix-only
if sys.platform != "win32":
    import fcntl
else:
    fcntl = None
from typing import Optional


DEFAULT_SESSION_DIR = os.path.expanduser("~/.contao-cli-agent")
DEFAULT_SESSION_FILE = os.path.join(DEFAULT_SESSION_DIR, "session.json")


def get_session_path(session_name: Optional[str] = None) -> str:
    if session_name:
        return os.path.join(DEFAULT_SESSION_DIR, f"{session_name}.json")
    return DEFAULT_SESSION_FILE


def save_session(config: dict, session_path: Optional[str] = None) -> str:
    """Save session config with file locking."""
    path = session_path or DEFAULT_SESSION_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.exists(path) and fcntl is not None:
        with open(path, "r+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                f.truncate()
                json.dump(config, f, indent=2)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    else:
        with open(path, "w") as f:
            json.dump(config, f, indent=2)
    return path


def load_session(session_path: Optional[str] = None) -> dict:
    """Load session config."""
    path = session_path or DEFAULT_SESSION_FILE
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def delete_session(session_path: Optional[str] = None):
    """Delete session file."""
    path = session_path or DEFAULT_SESSION_FILE
    if os.path.exists(path):
        os.remove(path)


def list_sessions() -> list:
    """List all saved sessions."""
    if not os.path.exists(DEFAULT_SESSION_DIR):
        return []
    sessions = []
    for f in Path(DEFAULT_SESSION_DIR).glob("*.json"):
        try:
            with open(f) as fp:
                cfg = json.load(fp)
            sessions.append({
                "name": f.stem,
                "host": cfg.get("host", "?"),
                "user": cfg.get("user", "?"),
                "contao_root": cfg.get("contao_root", "?"),
                "path": str(f),
            })
        except Exception:
            pass
    return sessions
