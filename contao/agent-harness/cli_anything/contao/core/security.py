"""Security operations."""
from cli_anything.contao.utils.contao_backend import ContaoBackend


def hash_password(backend: ContaoBackend, password: str, algorithm: str = "auto") -> dict:
    cmd = "security:hash-password --no-interaction"
    if algorithm != "auto":
        cmd += f" --algorithm={algorithm}"
    result = backend.run_raw(
        f'echo "{password}" | php bin/console {cmd}'
    )
    return {"output": result["stdout"].strip()}
