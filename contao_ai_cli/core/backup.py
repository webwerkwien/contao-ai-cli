"""Contao database backup management."""
import json
import shlex
from contao_ai_cli.utils.contao_backend import ContaoBackend


def backup_create(backend: ContaoBackend, name: str = "") -> dict:
    cmd = "contao:backup:create"
    if name:
        cmd += f" {shlex.quote(name)}"
    result = backend.run(cmd)
    return {"status": "created", "output": result["stdout"]}


def backup_list(backend: ContaoBackend) -> dict:
    result = backend.run("contao:backup:list")
    return {"output": result["stdout"]}


def backup_restore(backend: ContaoBackend, backup_name: str) -> dict:
    """Restore a backup Contao lists under exactly this name -- nothing else (v1.7.0).

    `contao:backup:restore` does not stop at a name it does not list: on
    showcase.conpai.eu a `.sql` for a `.sql.gz` played back the newest backup and was
    reported as restored under the name asked for (2026-10-13). A restore overwrites the
    whole database, so the name is checked against `contao:backup:list` first and a miss
    restores nothing.
    """
    try:
        listed = json.loads(backend.run("contao:backup:list --format=json")["stdout"] or "[]")
    except ValueError as e:
        return {"status": "error", "code": 1, "backup": backup_name,
                "message": f"The backup list could not be read ({e}); nothing was restored."}
    names = [b.get("name") for b in listed if isinstance(b, dict) and b.get("name")] if isinstance(listed, list) else []
    if backup_name not in names:
        return {"status": "error", "code": 1, "backup": backup_name, "available": names[:10],
                "message": f"No backup named {backup_name!r}; nothing was restored. Contao's restore would "
                           f"not refuse it but play back another backup. Use a name from `backup list`"
                           + (f", e.g. {names[0]} (newest)." if names else " -- there are none.")}
    cmd = f"contao:backup:restore {shlex.quote(backup_name)} --no-interaction"
    result = backend.run(cmd)
    return {"status": "restored", "backup": backup_name, "output": result["stdout"]}
