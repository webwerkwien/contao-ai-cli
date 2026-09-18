"""
connect, session-list, session-delete commands.
"""
import re

import click

from contao_ai_cli.utils.contao_backend import ContaoBackend, ContaoBackendError
from contao_ai_cli.core import session as session_mod
from contao_ai_cli.core.status import WARNING, collect_status, next_steps
from .helpers import _output


def _host_key_notice(stderr: str) -> str | None:
    """
    The 'Permanently added ...' line, if ssh reported a first contact.

    Measured against OpenSSH on 2026-09-02, the line reads:

        Warning: Permanently added 'c5.axeltest.at' (ED25519) to the list of known hosts.

    Matched on the stable middle of it rather than the whole sentence, so a
    reworded warning still registers as "a key was accepted". Returns None when
    the host was already known, which is the ordinary case.
    """
    for line in (stderr or "").splitlines():
        if "Permanently added" in line:
            return line.strip().removeprefix("Warning: ").strip()
    return None


def _msys_path_hint(root: str) -> str:
    """A hint when --root looks like Git Bash rewrote it, else ''.

    Measured on 2026-09-18: `connect --root /var/www/…` typed into Git Bash arrived as
    `C:/Program Files/Git/var/www/…` — MSYS turns an argument that starts with / into a
    Windows path. The server answered "cd: … No such file or directory" and nothing
    said why. Only on failure and only for the Git prefix: a Windows server with a real
    `C:\\…` root stays untouched.
    """
    normalized = root.replace("\\", "/")
    # The Git install dir (Program Files, a drive root, PortableGit) followed by a Unix
    # top-level directory — a real Windows root that merely sits in a folder called Git
    # does not continue with var/, home/ and the like (review before v0.27.0).
    if re.match(r"^[A-Za-z]:/(?:.*/)?(?:Portable)?Git/(?:var|home|srv|usr|opt|www|web|data|mnt|tmp|etc)/",
                normalized, re.IGNORECASE):
        return (" --root looks rewritten by Git Bash (MSYS turns a leading / into a Windows"
                " path). Run the command with MSYS_NO_PATHCONV=1 set, or from another shell.")
    return ""


@click.command()
@click.option("--host", required=True, help="SSH host")
@click.option("--user", required=True, help="SSH user")
@click.option("--root", required=True, help="Contao root path on server")
@click.option("--key", default=None, help="SSH private key path")
@click.option("--port", default=22, help="SSH port (default: 22)")
@click.option("--php", default="php", help="PHP binary (default: php)")
@click.option("--name", default=None, help="Session name (default: session)")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def connect(ctx, host, user, root, key, port, php, name, as_json):
    """Connect to a Contao installation, save the session and report what to do next.

    No questions (v0.21.0): connect runs once per site and was the only step that needed a
    terminal. The warning is in the answer; every setup step is its own command, listed
    in nextSteps for the agent to confirm with the user.
    """
    as_json = as_json or ctx.obj.get("as_json")
    session_path = session_mod.get_session_path(name)
    ssh = {"host": host, "user": user, "contao_root": root, "key_path": key, "port": port, "php_path": php}

    try:
        backend = ContaoBackend(**{k: v for k, v in ssh.items() if v is not None})
        probe = backend.run("--version")
    except ContaoBackendError as e:
        _output({"status": "error", "code": 1,
                 "message": f"Connection failed: {e}. No session was saved.{_msys_path_hint(root)}"},
                as_json)
        ctx.exit(1)

    # Reconnecting must not drop what the session already holds (bridge URL and token):
    # save_session truncates, and up to v0.20.0 a re-connect silently lost the bridge.
    # An unreadable file (empty, truncated) is replaced rather than a crash: reconnecting
    # is how a broken session gets fixed, and the old blind overwrite did exactly that
    # (review 2026-09-17).
    try:
        existing = session_mod.load_session(session_path)
        replaced = bool(existing)
    except (OSError, ValueError):
        existing, replaced = {}, True
    if not isinstance(existing, dict):
        existing = {}
    session_mod.save_session({**existing, **ssh}, session_path)

    state = collect_status(session_path)
    if state["core"].get("reachable"):
        cfg = session_mod.load_session(session_path)
        cfg["core_bundle_available"] = state["core"].get("installed") is not None
        cfg.pop("bridge_available", None)  # pre-0.5.0 name
        session_mod.save_session(cfg, session_path)

    data = {"status": "connected", "session": session_path, "replaced": replaced,
            "version": probe["stdout"].strip(), "warning": WARNING, "state": state,
            "nextSteps": next_steps(state, name)}

    # Audit 2026-09-02 (H-10). We connect with StrictHostKeyChecking=accept-new,
    # which is the right setting: measured against a live host, it still
    # refuses when a KNOWN key changes, and `yes` would - next to
    # BatchMode=yes, where ssh cannot ask - simply make every first
    # connection fail with no way forward.
    #
    # What was wrong was not the setting but the silence. ssh announces a
    # first contact ("Warning: Permanently added ... to the list of known
    # hosts"), and run() captured that on stderr and dropped it on success.
    # The user was told "connected" and never learned that a host key had
    # just been trusted on their behalf. Reporting it turns silent
    # trust-on-first-use into stated trust-on-first-use; it changes no
    # behaviour and breaks no first connection.
    new_host_key = _host_key_notice(probe.get("stderr", ""))
    if new_host_key:
        # Released in v0.20.0 as snake_case; a later rename to camelCase was an
        # undocumented break (review 2026-09-17). Restored to what callers were
        # actually shipped.
        data["host_key_accepted"] = new_host_key

    _output(data, as_json)


@click.command("session-list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def session_list(ctx, as_json):
    """List saved sessions."""
    sessions = session_mod.list_sessions()
    _output(sessions, as_json or ctx.obj.get("as_json"))


@click.command("session-delete")
@click.option("--name", default=None)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def session_delete(ctx, name, as_json):
    """Delete a session."""
    path = session_mod.get_session_path(name)
    session_mod.delete_session(path)
    _output({"status": "deleted", "path": path}, as_json or ctx.obj.get("as_json"))
