"""Contao backend user management."""
import json
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.utils.table_parser import parse_table


def user_list(backend: ContaoBackend) -> list:
    result = backend.run("contao:user:list --format=json")
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        parsed = parse_table(result["stdout"])
        return parsed if parsed else {"raw": result["stdout"]}


def user_create(backend: ContaoBackend, username: str, password: str,
                name: str, email: str, language: str = "en",
                admin: bool = False) -> dict:
    """Create a backend user. username, name, email, language, password are mandatory."""
    cmd = (f"contao:user:create "
           f"--username={username} "
           f"--password={password} "
           f"--name='{name}' "
           f"--email={email} "
           f"--language={language} "
           f"--no-interaction")
    if admin:
        cmd += " --admin"
    result = backend.run(cmd)
    return {"status": "created", "username": username, "output": result["stdout"]}


def user_password(backend: ContaoBackend, username: str, password: str) -> dict:
    # username is a positional argument, not a flag
    cmd = (f"contao:user:password "
           f"--password={password} "
           f"--no-interaction "
           f"{username}")
    result = backend.run(cmd)
    return {"status": "updated", "username": username, "output": result["stdout"]}
