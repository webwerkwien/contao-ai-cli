"""Contao frontend member management (tl_member)."""
import json
import shlex
from contao_ai_cli.utils.contao_backend import ContaoBackend, ContaoBackendError
from contao_ai_cli.core.contao_ops import record_list, run_json_or_raw, build_set_args, join_args


def member_list(backend: ContaoBackend, limit=None, offset=None) -> dict:
    """List front end members (tl_member)."""
    return record_list(
        backend, "tl_member",
        fields=["id", "username", "email", "firstname", "lastname", "disable"],
        limit=limit, offset=offset,
    )


MEMBER_PASSWORD_CORE = "0.26.0"


def _run_with_password(backend: ContaoBackend, cmd: str, password: str, command: str) -> dict:
    """Run a command that reads the password from stdin, and name a missing command plainly.

    The password travels on the ssh channel's stdin, never on a command line — neither the
    local ssh process's nor the remote php process's (audit 2026-09-02, H3).
    """
    try:
        result = backend.run(cmd, stdin_data=f"{password}\n")
    except ContaoBackendError as e:
        if "is not defined" in str(e) or "Unknown command" in str(e):
            raise ContaoBackendError(
                f"{command} is not available on this site. It needs contao-ai-core-bundle "
                f"v{MEMBER_PASSWORD_CORE} or newer: bundle update core."
            ) from e
        raise
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"raw": result["stdout"]}


def member_create(backend: ContaoBackend, username: str, password: str,
                  firstname: str, lastname: str, email: str, fields: dict | None = None) -> dict:
    """Create a front end member; core-bundle v0.26.0 checks and hashes the password.

    Until v0.27.0 this called `contao:member:create --password=…`, a command the
    core-bundle never had: every call failed, with a message that promised it for "v1.x+".
    Found in the regression run before 1.0 (2026-09-18). The password was also meant to
    go onto the command line (the H3 TODO that stood here). Now it goes on stdin.
    """
    cmd = join_args(
        "contao:member:create",
        f"--username={shlex.quote(username)}",
        f"--firstname={shlex.quote(firstname)}",
        f"--lastname={shlex.quote(lastname)}",
        f"--email={shlex.quote(email)}",
        build_set_args(fields or {}),
        "--password-stdin",
        "--no-interaction",
    )
    return _run_with_password(backend, cmd, password, "contao:member:create")


def member_password(backend: ContaoBackend, username: str, password: str) -> dict:
    """Set a front end member's password — Contao has a console command only for back end users."""
    cmd = join_args("contao:member:password", shlex.quote(username), "--password-stdin", "--no-interaction")
    return _run_with_password(backend, cmd, password, "contao:member:password")


def member_update(backend: ContaoBackend, username: str, fields: dict) -> dict:
    """Update frontend member fields via contao-ai-core-bundle."""
    set_args = build_set_args(fields)
    cmd = join_args("contao:member:update", shlex.quote(username), set_args, "--no-interaction")
    return run_json_or_raw(backend, cmd)


def member_delete(backend: ContaoBackend, username: str) -> dict:
    """Delete a frontend member via contao-ai-core-bundle."""
    return run_json_or_raw(backend, f"contao:member:delete {shlex.quote(username)} --no-interaction")
