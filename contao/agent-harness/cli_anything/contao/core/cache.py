"""Cache management commands for Contao 5."""
from cli_anything.contao.utils.contao_backend import ContaoBackend


def cache_clear(backend: ContaoBackend) -> dict:
    result = backend.run("cache:clear")
    return {"status": "cleared", "output": result["stdout"]}


def cache_warmup(backend: ContaoBackend) -> dict:
    result = backend.run("cache:warmup")
    return {"status": "warmed", "output": result["stdout"]}


def cache_pool_list(backend: ContaoBackend) -> list:
    result = backend.run("cache:pool:list")
    lines = [l.strip() for l in result["stdout"].splitlines() if l.strip() and not l.startswith("-")]
    pools = [l for l in lines if l and not l.startswith("Pool")]
    return {"pools": pools, "raw": result["stdout"]}


def cache_pool_clear(backend: ContaoBackend, pool: str = "cache.global_clearer") -> dict:
    result = backend.run(f"cache:pool:clear {pool}")
    return {"status": "cleared", "pool": pool, "output": result["stdout"]}
