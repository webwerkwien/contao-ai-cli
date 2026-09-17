"""Cache management commands for Contao 5."""
import json
import shlex
from contao_ai_cli.utils.contao_backend import ContaoBackend, ContaoBackendError


def cache_clear(backend: ContaoBackend) -> dict:
    """Clear the cache -- logged in tl_log as the back end does (core-bundle v0.21.0).

    Symfony's `cache:clear` leaves no trace; the audit of the ConpAI acceptance test found
    it the only unlogged step of a whole build (Nr. 50, 2026-09-17). `contao:cache:clear`
    runs it and writes "Purged the internal cache". On an older core bundle the plain
    `cache:clear` still runs, and `logged: false` says what is missing.
    """
    result = backend.run("contao:cache:clear", check=False)
    if result.get("returncode", 0) == 0:
        try:
            data = json.loads(result["stdout"])
            return {"status": "cleared", "output": data.get("output", ""), "logged": bool(data.get("logged"))}
        except (json.JSONDecodeError, AttributeError):
            pass
    if backend.undefined_contao_command(f"{result.get('stdout', '')}\n{result.get('stderr', '')}"):
        plain = backend.run("cache:clear")
        return {"status": "cleared", "output": plain["stdout"], "logged": False}
    # The core bundle answers an error as JSON; its message, not a cut-off document.
    try:
        detail = json.loads(result.get("stdout") or "")["message"]
    except (json.JSONDecodeError, TypeError, KeyError):
        detail = (result.get("stderr") or result.get("stdout") or "")[:500]
    raise ContaoBackendError(f"cache clear failed (exit {result.get('returncode')}): {detail}")


def cache_warmup(backend: ContaoBackend) -> dict:
    result = backend.run("cache:warmup")
    return {"status": "warmed", "output": result["stdout"]}


def cache_pool_list(backend: ContaoBackend) -> list:
    result = backend.run("cache:pool:list")
    lines = [l.strip() for l in result["stdout"].splitlines() if l.strip() and not l.startswith("-")]
    pools = [l for l in lines if l and not l.startswith("Pool")]
    return {"pools": pools, "raw": result["stdout"]}


def cache_pool_clear(backend: ContaoBackend, pool: str = "cache.global_clearer") -> dict:
    result = backend.run(f"cache:pool:clear {shlex.quote(pool)}")
    return {"status": "cleared", "pool": pool, "output": result["stdout"]}
