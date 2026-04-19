"""Search index operations (cmsig/seal)."""
import shlex
from cli_anything.contao.utils.contao_backend import ContaoBackend


def search_reindex(backend: ContaoBackend, index: str = "") -> dict:
    cmd = "cmsig:seal:reindex --no-interaction"
    if index:
        cmd += f" --index={shlex.quote(index)}"
    result = backend.run(cmd)
    return {"status": "ok", "output": result["stdout"]}


def search_index_create(backend: ContaoBackend, index: str = "") -> dict:
    cmd = "cmsig:seal:index-create --no-interaction"
    if index:
        cmd += f" --index={shlex.quote(index)}"
    result = backend.run(cmd)
    return {"status": "ok", "output": result["stdout"]}


def search_index_drop(backend: ContaoBackend, index: str = "") -> dict:
    cmd = "cmsig:seal:index-drop --no-interaction"
    if index:
        cmd += f" --index={shlex.quote(index)}"
    result = backend.run(cmd)
    return {"status": "ok", "output": result["stdout"]}
