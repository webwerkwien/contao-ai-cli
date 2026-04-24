"""Contao frontend member management (tl_member)."""
import shlex
from cli_anything.contao.utils.contao_backend import ContaoBackend, ContaoBackendError  # noqa: F401
from cli_anything.contao.core.contao_ops import run_sql_table, run_json_or_raw, build_set_args


def _q(s: str) -> str:
    """Escape a string value for SQL single-quoted literals."""
    return s.replace("'", "''")


def member_list(backend: ContaoBackend) -> list:
    try:
        result = backend.run("contao:member:list --format=json")
        import json
        return json.loads(result["stdout"])
    except (ContaoBackendError, Exception):
        pass
    # No native member:list command — fall back to direct SQL
    sql = "SELECT id, username, email, firstname, lastname, disable FROM tl_member"
    return run_sql_table(backend, sql)


def member_create(backend: ContaoBackend, username: str, password: str,
                  firstname: str, lastname: str, email: str) -> dict:
    escaped = password.replace("'", "'\\''")
    hash_result = backend.run_raw(
        f"php -r \"echo password_hash('{escaped}', PASSWORD_DEFAULT);\""
    )
    pw_hash = hash_result["stdout"].strip()

    sql = (
        f"INSERT INTO tl_member "
        f"(username, password, firstname, lastname, email, dateAdded, tstamp) "
        f"VALUES ('{_q(username)}', '{_q(pw_hash)}', '{_q(firstname)}', '{_q(lastname)}', '{_q(email)}', "
        f"UNIX_TIMESTAMP(), UNIX_TIMESTAMP())"
    )
    backend.run(f'doctrine:query:sql {shlex.quote(sql)}')
    return {"status": "created", "username": username}


def member_update(backend: ContaoBackend, username: str, fields: dict) -> dict:
    """Update frontend member fields via contao-cli-bridge."""
    set_args = build_set_args(fields)
    return run_json_or_raw(backend, f"contao:member:update {shlex.quote(username)} {set_args} --no-interaction")


def member_delete(backend: ContaoBackend, username: str) -> dict:
    """Delete a frontend member via contao-cli-bridge."""
    return run_json_or_raw(backend, f"contao:member:delete {shlex.quote(username)} --no-interaction")
