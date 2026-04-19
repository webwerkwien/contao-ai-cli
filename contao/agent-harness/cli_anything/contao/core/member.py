"""Contao frontend member management (tl_member)."""
import json
import shlex
from cli_anything.contao.utils.contao_backend import ContaoBackend, ContaoBackendError  # noqa: F401
from cli_anything.contao.utils.table_parser import parse_table


def member_list(backend: ContaoBackend) -> list:
    try:
        result = backend.run("contao:member:list --format=json")
        return json.loads(result["stdout"])
    except (ContaoBackendError, json.JSONDecodeError):
        pass
    # No native member:list command — fall back to direct SQL
    result = backend.run(
        'doctrine:query:sql '
        '"SELECT id, username, email, firstname, lastname, disable FROM tl_member"'
    )
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}


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
        f"VALUES ('{username}', '{pw_hash}', '{firstname}', '{lastname}', '{email}', "
        f"UNIX_TIMESTAMP(), UNIX_TIMESTAMP())"
    )
    backend.run(f'doctrine:query:sql "{sql}"')
    return {"status": "created", "username": username}


def member_update(backend: ContaoBackend, username: str, fields: dict) -> dict:
    """Update frontend member fields via contao-cli-bridge."""
    set_args = " ".join(f"--set {shlex.quote(f'{k}={v}')}" for k, v in fields.items())
    result = backend.run(f"contao:member:update {shlex.quote(username)} {set_args} --no-interaction")
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"status": "ok", "output": result["stdout"]}


def member_delete(backend: ContaoBackend, username: str) -> dict:
    """Delete a frontend member via contao-cli-bridge."""
    result = backend.run(f"contao:member:delete {shlex.quote(username)} --no-interaction")
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"status": "ok", "output": result["stdout"]}
