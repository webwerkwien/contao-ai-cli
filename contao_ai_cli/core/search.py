"""Search index operations (cmsig/seal)."""
import shlex
from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import run_json_or_raw


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


def search_query(backend: ContaoBackend, query: str, limit=None) -> dict:
    """Search the Contao fulltext index.

    The group had three commands for maintaining the index and none for
    querying it, although the server has had contao:search:query all along.
    It surfaced when `ext list` was built and asked the installation what it
    offers that this CLI cannot reach.
    """
    cmd = f"contao:search:query {shlex.quote(query)}"
    if limit is not None:
        cmd += f" --limit={int(limit)}"
    return run_json_or_raw(backend, cmd)
