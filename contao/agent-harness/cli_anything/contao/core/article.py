"""Contao article management (tl_article)."""
import shlex
from cli_anything.contao.utils.contao_backend import ContaoBackend
from cli_anything.contao.core.contao_ops import run_sql_table, run_json_or_raw, build_set_args


def article_list(backend: ContaoBackend, page_id: int = None) -> list:
    """List articles. Optionally filter by page ID (pid)."""
    where = f"WHERE pid = {int(page_id)}" if page_id is not None else ""
    sql = f"SELECT id, pid, title, alias, published, inColumn FROM tl_article {where} ORDER BY pid, sorting"
    return run_sql_table(backend, sql)


def article_read(backend: ContaoBackend, article_id: int) -> dict:
    """Read all fields of a tl_article record."""
    return run_json_or_raw(backend, f"contao:article:read {article_id}")


def article_create(backend: ContaoBackend, title: str, pid: int,
                   in_column: str = "main", fields: dict = None) -> dict:
    """Create an article via contao-cli-bridge."""
    cmd = (f"contao:article:create --title={shlex.quote(title)} --pid={pid} "
           f"--inColumn={shlex.quote(in_column)} --no-interaction")
    if fields:
        cmd += " " + build_set_args(fields)
    return run_json_or_raw(backend, cmd)
