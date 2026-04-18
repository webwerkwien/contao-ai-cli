"""Contao article management (tl_article)."""
import json
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.utils.table_parser import parse_table


def article_list(backend: ContaoBackend, page_id: int = None) -> list:
    """List articles. Optionally filter by page ID (pid)."""
    where = f"WHERE pid = {page_id}" if page_id is not None else ""
    sql = f"SELECT id, pid, title, alias, published, inColumn FROM tl_article {where} ORDER BY pid, sorting"
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}


def article_create(backend: ContaoBackend, title: str, pid: int,
                   in_column: str = "main", fields: dict = None) -> dict:
    """Create an article via contao-cli-bridge."""
    cmd = (f"contao:article:create --title='{title}' --pid={pid} "
           f"--inColumn={in_column} --no-interaction")
    if fields:
        cmd += " " + " ".join(f"--set {k}={v}" for k, v in fields.items())
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"status": "ok", "output": result["stdout"]}
