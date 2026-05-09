"""
HTTP client for the contao-ai-backend-bundle CLI bridge (Phase 10.1+).

Endpoint: POST <server>/_ai_cli/macro
Auth:     Authorization: Bearer <userId>.<random>

The bridge dispatches Phase-9 macro tools (record_clone, record_rewrite)
server-side, so a Bulk-LLM job runs once on the server with full Voter
pipeline + tl_version audit, instead of N round-trips through SSH+console.

No third-party HTTP dependency — pure stdlib (urllib) keeps the CLI
install footprint identical to before. Bridge is optional; if the user
never configures `bridge_url`/`bridge_token`, the rest of the CLI is
unchanged.
"""
import json
import urllib.error
import urllib.request
from typing import Any


class BridgeError(Exception):
    """Bridge call failed. `.status` is the HTTP code, `.payload` the parsed JSON if any."""

    def __init__(self, message: str, status: int | None = None, payload: dict | None = None):
        super().__init__(message)
        self.status = status
        self.payload = payload or {}


class BackendBridgeClient:
    def __init__(self, base_url: str, token: str, timeout: int = 120):
        if not base_url or not token:
            raise ValueError("BackendBridgeClient requires base_url and token")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def clone(
        self,
        table: str,
        source_id: int,
        modifications: dict | None = None,
        recursive: bool = False,
    ) -> dict:
        payload = {
            "tool": "record_clone",
            "table": table,
            "sourceId": int(source_id),
            "modifications": modifications or {},
            "recursive": bool(recursive),
        }
        return self._call(payload)

    def rewrite(
        self,
        table: str,
        record_id: int,
        instructions: str,
        recursive: bool = False,
    ) -> dict:
        payload = {
            "tool": "record_rewrite",
            "table": table,
            "id": int(record_id),
            "instructions": instructions,
            "recursive": bool(recursive),
        }
        return self._call(payload)

    def _call(self, payload: dict) -> dict:
        url = f"{self.base_url}/_ai_cli/macro"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                # Bridge hat einen 32 KB Body-Cap; größere Macros sollen scheitern,
                # nicht stillschweigend truncated werden — kein gzip-Encoding nötig.
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                status = resp.getcode()
        except urllib.error.HTTPError as e:
            raw = (e.read() or b"").decode("utf-8", errors="replace")
            status = e.code
        except urllib.error.URLError as e:
            raise BridgeError(f"Bridge unreachable: {e.reason}") from e

        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError as e:
            raise BridgeError(
                f"Bridge returned non-JSON (status {status}): {raw[:200]}",
                status=status,
            ) from e

        if status >= 400 or data.get("status") == "error":
            raise BridgeError(
                data.get("message") or f"Bridge call failed (status {status})",
                status=status,
                payload=data,
            )

        return data


def from_session_config(cfg: dict) -> BackendBridgeClient:
    """Build a client from the session JSON. Raises ValueError if not configured."""
    url = cfg.get("bridge_url")
    token = cfg.get("bridge_token")
    if not url or not token:
        raise ValueError(
            "Bridge not configured. Run: contao-ai-cli bridge configure --url <url> --token <token>"
        )
    return BackendBridgeClient(url, token)


def mask_token(token: str) -> str:
    """Mask a bridge token for display: '5.abc…xyz' style."""
    if not token or "." not in token:
        return "***"
    prefix, secret = token.split(".", 1)
    if len(secret) <= 8:
        return f"{prefix}.***"
    return f"{prefix}.{secret[:4]}...{secret[-4:]}"
