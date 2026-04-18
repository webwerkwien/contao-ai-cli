"""Contao frontend member management (tl_member)."""
import json
from cli_anything.contao.utils.contao_backend import ContaoBackend, ContaoBackendError


def member_list(backend: ContaoBackend) -> list:
    try:
        result = backend.run("contao:member:list --format=json")
    except ContaoBackendError:
        # No native member:list command — fall back to direct SQL
        result = backend.run(
            'doctrine:query:sql '
            '"SELECT id, username, email, firstname, lastname, disable FROM tl_member"'
        )
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"raw": result["stdout"]}


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
