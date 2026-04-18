"""Contao page management (tl_page)."""
import json
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.utils.table_parser import parse_table


def page_list(backend: ContaoBackend, pid: int = None) -> list:
    """List pages. Optionally filter by parent ID."""
    where = f"WHERE pid = {pid}" if pid is not None else ""
    sql = f"SELECT id, pid, title, alias, type, published, hide FROM tl_page {where} ORDER BY sorting"
    result = backend.run(f'doctrine:query:sql "{sql}"')
    parsed = parse_table(result["stdout"])
    return parsed if parsed else {"raw": result["stdout"]}


def page_tree(backend: ContaoBackend) -> list:
    """
    Return page tree as nested list of dicts.
    Each page has a 'children' key with sub-pages.
    """
    sql = "SELECT id, pid, title, alias, type, published FROM tl_page ORDER BY sorting"
    result = backend.run(f'doctrine:query:sql "{sql}"')
    pages = parse_table(result["stdout"])
    if not isinstance(pages, list):
        return pages  # error fallback

    by_id = {}
    for p in pages:
        p = dict(p)
        p["id"] = int(p["id"])
        p["pid"] = int(p["pid"])
        p["children"] = []
        by_id[p["id"]] = p

    roots = []
    for p in by_id.values():
        if p["pid"] == 0:
            roots.append(p)
        elif p["pid"] in by_id:
            by_id[p["pid"]]["children"].append(p)

    return roots


def page_create(backend: ContaoBackend, title: str, pid: int = 0,
                type: str = "regular", alias: str = "", language: str = "de",
                fields: dict = None) -> dict:
    """Create a page via contao-cli-bridge."""
    cmd = (f"contao:page:create --title='{title}' --pid={pid} "
           f"--type={type} --language={language} --no-interaction")
    if alias:
        cmd += f" --alias={alias}"
    if fields:
        cmd += " " + " ".join(f"--set {k}={v}" for k, v in fields.items())
    result = backend.run(cmd)
    try:
        return json.loads(result["stdout"])
    except json.JSONDecodeError:
        return {"status": "ok", "output": result["stdout"]}
