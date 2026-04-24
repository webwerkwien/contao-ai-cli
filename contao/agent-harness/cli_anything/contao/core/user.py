"""Contao backend user management."""
import shlex
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.core.contao_ops import run_sql_table, run_json_or_raw, build_set_args


def user_list(backend: ContaoBackend) -> list:
    return run_json_or_raw(backend, "contao:user:list --format=json")


def user_create(backend: ContaoBackend, username: str, password: str,
                name: str, email: str, language: str = "en",
                admin: bool = False) -> dict:
    """Create a backend user. username, name, email, language, password are mandatory.

    TODO (H3): --password= is visible in SSH command logs and /proc/cmdline.
    Real fix requires Contao command to support --password-stdin or reading from
    an env var directly (not via shell expansion into argv).
    """
    cmd = (f"contao:user:create "
           f"--username={shlex.quote(username)} "
           f"--password={shlex.quote(password)} "
           f"--name={shlex.quote(name)} "
           f"--email={shlex.quote(email)} "
           f"--language={shlex.quote(language)} "
           f"--no-interaction")
    if admin:
        cmd += " --admin"
    result = backend.run(cmd)
    return {"status": "created", "username": username, "output": result["stdout"]}


def user_update(backend: ContaoBackend, username: str, fields: dict) -> dict:
    """Update backend user fields via contao-cli-bridge."""
    set_args = build_set_args(fields)
    cmd = f"contao:user:update {shlex.quote(username)} {set_args} --no-interaction"
    return run_json_or_raw(backend, " ".join(cmd.split()))


def user_delete(backend: ContaoBackend, username: str) -> dict:
    """Delete a backend user via contao-cli-bridge."""
    return run_json_or_raw(backend, f"contao:user:delete {shlex.quote(username)} --no-interaction")


def user_password(backend: ContaoBackend, username: str, password: str) -> dict:
    # TODO (H3): --password= visible in /proc/cmdline; long-term fix = --password-stdin
    # username is a positional argument, not a flag
    cmd = (f"contao:user:password "
           f"--password={shlex.quote(password)} "
           f"--no-interaction "
           f"{shlex.quote(username)}")
    result = backend.run(cmd)
    return {"status": "updated", "username": username, "output": result["stdout"]}
