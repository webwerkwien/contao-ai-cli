"""
Session management for contao-ai-cli.
Stores SSH connection config and provides session file locking.
"""
import json
import os
from pathlib import Path

DEFAULT_SESSION_DIR = os.path.expanduser("~/.contao-ai-cli")
DEFAULT_SESSION_FILE = os.path.join(DEFAULT_SESSION_DIR, "session.json")


def get_session_path(session_name: str | None = None) -> str:
    if session_name:
        return os.path.join(DEFAULT_SESSION_DIR, f"{session_name}.json")
    return DEFAULT_SESSION_FILE


def save_session(config: dict, session_path: str | None = None) -> str:
    """Save session config with restricted permissions (owner-read-only, 0o600)."""
    path = session_path or DEFAULT_SESSION_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(config, f, indent=2)
    return path


def load_session(session_path: str | None = None) -> dict:
    """Load session config."""
    path = session_path or DEFAULT_SESSION_FILE
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def delete_session(session_path: str | None = None):
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
