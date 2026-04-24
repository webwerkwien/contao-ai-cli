"""Contao frontend member management (tl_member)."""
import json
import shlex
from cli_anything.contao.utils.contao_backend import ContaoBackend, ContaoBackendError
from cli_anything.contao.core.contao_ops import run_sql_table, run_json_or_raw, build_set_args


def member_list(backend: ContaoBackend) -> list:
    try:
        result = backend.run("contao:member:list --format=json")
        return json.loads(result["stdout"])
    except (ContaoBackendError, json.JSONDecodeError):
        pass
    # No native member:list command — fall back to direct SQL
    sql = "SELECT id, username, email, firstname, lastname, disable FROM tl_member"
    return run_sql_table(backend, sql)


def member_create(backend: ContaoBackend, username: str, password: str,
                  firstname: str, lastname: str, email: str) -> dict:
    """Create a frontend member via contao-ai-core-bundle (handles password hashing server-side).

    TODO (H3): --password= is visible in SSH command logs and /proc/cmdline.
    Real fix requires the bridge command to support --password-stdin.
    """
    cmd = (
        f"contao:member:create "
        f"--username={shlex.quote(username)} "
        f"--password={shlex.quote(password)} "
        f"--firstname={shlex.quote(firstname)} "
        f"--lastname={shlex.quote(lastname)} "
        f"--email={shlex.quote(email)} "
        f"--no-interaction"
    )
    try:
        return run_json_or_raw(backend, cmd)
    except ContaoBackendError as e:
        if "is not defined" in str(e) or "Unknown command" in str(e):
            raise ContaoBackendError(
                "contao:member:create not available. Update contao-ai-core-bundle to v1.x+"
            ) from e
        raise


def member_update(backend: ContaoBackend, username: str, fields: dict) -> dict:
    """Update frontend member fields via contao-ai-core-bundle."""
    set_args = build_set_args(fields)
    cmd = f"contao:member:update {shlex.quote(username)} {set_args} --no-interaction"
    return run_json_or_raw(backend, " ".join(cmd.split()))


def member_delete(backend: ContaoBackend, username: str) -> dict:
    """Delete a frontend member via contao-ai-core-bundle."""
    return run_json_or_raw(backend, f"contao:member:delete {shlex.quote(username)} --no-interaction")
