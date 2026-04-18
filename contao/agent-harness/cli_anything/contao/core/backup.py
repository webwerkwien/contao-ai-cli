"""Contao database backup management."""
from cli_anything.contao.utils.contao_backend import ContaoBackend


def backup_create(backend: ContaoBackend, name: str = "") -> dict:
    cmd = "contao:backup:create"
    if name:
        cmd += f" {name}"
    result = backend.run(cmd)
    return {"status": "created", "output": result["stdout"]}


def backup_list(backend: ContaoBackend) -> dict:
    result = backend.run("contao:backup:list")
    return {"output": result["stdout"]}


def backup_restore(backend: ContaoBackend, backup_name: str) -> dict:
    cmd = f"contao:backup:restore {backup_name} --no-interaction"
    result = backend.run(cmd)
    return {"status": "restored", "backup": backup_name, "output": result["stdout"]}
