"""Debug and inspection commands for Contao 5."""
import shlex
from cli_anything.contao.utils.contao_backend import ContaoBackend


def debug_contao_twig(backend: ContaoBackend) -> dict:
    result = backend.run("debug:contao-twig")
    return {"output": result["stdout"]}


def debug_dca(backend: ContaoBackend, table: str) -> dict:
    result = backend.run(f"debug:dca {shlex.quote(table)}")
    return {"table": table, "output": result["stdout"]}


def debug_pages(backend: ContaoBackend) -> dict:
    result = backend.run("debug:pages")
    return {"output": result["stdout"]}


def debug_fragments(backend: ContaoBackend) -> dict:
    result = backend.run("debug:fragments")
    return {"output": result["stdout"]}


def debug_router(backend: ContaoBackend, path: str = "") -> dict:
    cmd = "debug:router"
    if path:
        cmd = f"router:match {shlex.quote(path)}"
    result = backend.run(cmd)
    return {"output": result["stdout"]}


def debug_plugins(backend: ContaoBackend) -> dict:
    result = backend.run("debug:plugins")
    return {"output": result["stdout"]}
