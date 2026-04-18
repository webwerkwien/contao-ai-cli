"""Mailer operations."""
from cli_anything.contao.utils.contao_backend import ContaoBackend


def mailer_test(backend: ContaoBackend, to: str) -> dict:
    result = backend.run(f"mailer:test --to={to} --no-interaction")
    return {"status": "ok", "to": to, "output": result["stdout"]}
