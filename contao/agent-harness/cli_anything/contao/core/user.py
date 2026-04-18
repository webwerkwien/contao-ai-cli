"""Contao backend user management."""
import json
from cli_anything.contao.utils.contao_backend import ContaoBackend


def user_list(backend: ContaoBackend) -> list:
    result = backend.run("contao:user:list --format=json")
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"raw": result["stdout"]}


def user_create(backend: ContaoBackend, username: str, password: str,
                name: str = "", email: str = "", admin: bool = False) -> dict:
    cmd = (f"contao:user:create "
           f"--username={username} "
           f"--password={password} "
           f"--no-interaction")
    if name:
        cmd += f" --name={name!r}"
    if email:
        cmd += f" --email={email}"
    if admin:
        cmd += " --admin"
    result = backend.run(cmd)
    return {"status": "created", "username": username, "output": result["stdout"]}


def user_password(backend: ContaoBackend, username: str, password: str) -> dict:
    cmd = (f"contao:user:password "
           f"--username={username} "
           f"--password={password} "
           f"--no-interaction")
    result = backend.run(cmd)
    return {"status": "updated", "username": username, "output": result["stdout"]}
