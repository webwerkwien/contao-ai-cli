"""Contao page management (tl_page)."""
import shlex
from contao_ai_cli.utils.contao_backend import ContaoBackend
from contao_ai_cli.core.contao_ops import (
    run_sql_table, run_json_or_raw, build_set_args, run_update, run_delete, run_publish,
)


def page_list(backend: ContaoBackend, pid: int | None = None) -> list:
    """List pages. Optionally filter by parent ID."""
    where = f"WHERE pid = {int(pid)}" if pid is not None else ""
    sql = f"SELECT id, pid, title, alias, type, published, hide FROM tl_page {where} ORDER BY sorting"
    return run_sql_table(backend, sql)


def page_tree(backend: ContaoBackend) -> list:
    """
    Return page tree as nested list of dicts.
    Each page has a 'children' key with sub-pages.
    """
    sql = "SELECT id, pid, title, alias, type, published FROM tl_page ORDER BY sorting"
    pages = run_sql_table(backend, sql)
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


def page_read(backend: ContaoBackend, page_id: int) -> dict:
    """Read all fields of a tl_page record incl. resolved effective layout."""
    return run_json_or_raw(backend, f"contao:page:read {page_id}")


def page_create(backend: ContaoBackend, title: str, pid: int = 0,
                type: str = "regular", alias: str = "", language: str = "de",
                fields: dict | None = None) -> dict:
    """Create a page via contao-ai-core-bundle."""
    cmd = (f"contao:page:create --title={shlex.quote(title)} --pid={pid} "
           f"--type={shlex.quote(type)} --language={shlex.quote(language)} --no-interaction")
    if alias:
        cmd += f" --alias={shlex.quote(alias)}"
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)


def page_update(backend: ContaoBackend, page_id: int, fields: dict) -> dict:
    """Update page fields via contao-ai-core-bundle."""
    return run_update(backend, "contao:page:update", page_id, fields)


def page_delete(backend: ContaoBackend, page_id: int) -> dict:
    """
    Delete a page via contao-ai-core-bundle.
    Cascades to the subpage tree, its articles and their content elements.
    Recoverable from the back end's "Restore" module.
    """
    return run_delete(backend, "contao:page:delete", page_id)


def page_publish(backend: ContaoBackend, page_id: int, published: bool = True) -> dict:
    """Publish or unpublish a page via contao-ai-core-bundle."""
    return run_publish(backend, "contao:page:publish", page_id, published)
