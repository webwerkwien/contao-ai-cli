"""Mailer operations."""
import shlex
from cli_anything.contao.utils.contao_backend import ContaoBackend


def mailer_test(backend: ContaoBackend, to: str) -> dict:
    result = backend.run(f"mailer:test --to={shlex.quote(to)} --no-interaction")
    return {"status": "ok", "to": to, "output": result["stdout"]}
